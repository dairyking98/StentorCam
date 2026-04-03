#!/usr/bin/env python3

'''
stentTrack.py - main stentor tracking / morphology script

Overview :

This script processes mp4 videos of single stentor in well plates
tracks single cells through the video, detects morphology parameters,
generates overlay video for debugging, creates output csv to store all params collected

Step outline
all frames 
- background subtraction
per frame
- contour extraction
- pose classification (contracted vs elongated)
- head/tail detection
- motion direction estimate
full video
- overlay generation
- csv output generation


Inputs : 
--video     : Input video file
--output    : Output CSV file path
--overlay   : Output overlay video path
--thresh    : Percentile threshold for foreground segmentation
--min_area  : Minimum contour area to consider 

Outputs : 
--output    : CSV file with per-frame tracking data
--overlay   : Overlay video with annotations


Example Usage (on command line) :
python stentTrack.py --output stentTrack.csv --overlay stentTrack.mp4 --thresh 99.5 --video video_path.mp4

Debugging : 
"#debugging ..." may be found in the code 
these are current working adjustments that are not important for functionality

'''

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
import argparse
import math
from collections import deque
import os
import subprocess

# ----------------------------
# Utility functions
# ----------------------------

def compute_centroid(contour):
    """
    Compute centroid (x, y) of a contour using image moments.

    Returns:
        (float, float): centroid coordinates or (nan, nan) if undefined
    """

    M = cv2.moments(contour)
    if M["m00"] == 0:
        return np.nan, np.nan
    return M["m10"] / M["m00"], M["m01"] / M["m00"]


def contour_to_string(contour):
    """
    Convert contour points to a compact string representation.

    Useful for storing contours in CSV.

    Returns:
        str: "x1,y1;x2,y2;..."
    """

    return ";".join([f"{int(p[0][0])},{int(p[0][1])}" for p in contour])


def motion_direction(prev_xy, curr_xy):
    """
    Compute direction of motion between two points.

    Based on angle between current and previous centroid coordinates.

    Returns:
        float: angle in degrees (NaN if undefined)
    """

    if prev_xy is None or np.any(np.isnan(curr_xy)):
        return np.nan
    dx = curr_xy[0] - prev_xy[0]
    dy = curr_xy[1] - prev_xy[1]
    if dx == 0 and dy == 0:
        return np.nan
    return math.degrees(math.atan2(dy, dx))


def draw_arrow(img, start, angle, length=30, color=(255, 255, 0, 255)):
    """
    Draw motion direction arrow on overlay.

    Returns:
        None: draws arrow directly to overlay
    """
    if np.isnan(angle):
        return
    end = (
        int(start[0] + length * math.cos(math.radians(angle))),
        int(start[1] + length * math.sin(math.radians(angle)))
    )
    cv2.arrowedLine(img, start, end, color, 2, tipLength=0.3)


def unit(v):
    """
    Normalize a vector.
    """

    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def angle_between(v1, v2):
    """
    Compute angle (radians) between two vectors.
    """
    v1 = unit(v1)
    v2 = unit(v2)
    dot = np.clip(np.dot(v1, v2), -1, 1)
    return math.acos(dot)


# ----------------------------
# Pose detection
# ----------------------------

def determine_pose(contour, pose_thresh=0.04):  
    """
    Classify contour shape as CONTRACTED or ELONGATED.

    Method :

    - Fit ellipse to contour
    - Compare contour points to ellipse perimeter
    - Compute error and normalize by contour/ellipse size
    - Uses threshold determined by disrtibution analysis to classify pose

    Args:
        contour (ndarray): contour points
        pose_thresh (float): threshold for classification

    Returns:
        pose (str): "CONTRACTED" or "ELONGATED"
        rect (tuple): bounding rectangle
        box (ndarray): rectangle corner points
        norm_error (float): normalized ellipse fitting error
    """

    # Generate bounding rect
    rect = cv2.minAreaRect(contour)

    (cx, cy), (w, h), angle = rect
    box = cv2.boxPoints(rect)
    box = np.asarray(box)

    # Fit ellipse to contour
    ellipse = cv2.fitEllipse(contour)
    (cx, cy), (MA, ma), angle = ellipse

    # Generate points on ellipse
    theta = np.linspace(0, 2*np.pi, 500)

    cos_a = np.cos(np.deg2rad(angle))
    sin_a = np.sin(np.deg2rad(angle))

    a = MA / 2.0
    b = ma / 2.0

    ellipse_pts = np.vstack([
        a * np.cos(theta),
        b * np.sin(theta)
    ]).T

    # Rotate + translate
    R = np.array([[cos_a, -sin_a],
                  [sin_a,  cos_a]])

    ellipse_pts = ellipse_pts @ R.T
    ellipse_pts[:, 0] += cx
    ellipse_pts[:, 1] += cy

    # Compute distance from contour points to ellipse curve
    contour_pts = contour.reshape(-1, 2)

    # For each contour point, find closest ellipse point
    dists = np.linalg.norm(
        contour_pts[:, None, :] - ellipse_pts[None, :, :],
        axis=2
    )

    min_dists = dists.min(axis=1)

    mean_error = min_dists.mean()

    # Normalize by ellipse size
    scale = 0.5 * (a + b)
    norm_error = mean_error / scale

    pose = "CONTRACTED" if norm_error < pose_thresh else "ELONGATED"

    return pose, rect, box, norm_error


# ----------------------------
# Adaptive triangle head scoring
# ----------------------------

def backwards_score(triangle, centroid, direction_deg):
    """
    Score triangle edges assuming backward motion.

    Used when forward confidence is low.

    See "find_head_tail_from_triangle_weighted" for more info
    """
    theta = math.radians(direction_deg)
    motion_vec = np.array([math.cos(theta), math.sin(theta)])
    motion_vec = -motion_vec

    edges = []
    for i in range(3):
        p1 = triangle[i]
        p2 = triangle[(i + 1) % 3]
        length = np.linalg.norm(p2 - p1)
        midpoint = (p1 + p2) / 2
        vec_to_mid = midpoint - centroid
        ang = angle_between(motion_vec, vec_to_mid)
        edges.append((i, p1, p2, length, ang))

    lengths = np.array([e[3] for e in edges])

    angles = np.array([a[4] for a in edges])


    # --- Compute how dominant the shortest edge is ---
    shortest = lengths.min()
    mean_other = np.mean(lengths[lengths != shortest]) if np.sum(lengths != shortest) else shortest
    dominance_ratio = shortest / (mean_other * 1.5 + 1e-6)

    # dominance_ratio → 0 means one edge is very small
    # dominance_ratio → 1 means edges similar

    w_len = 1 - dominance_ratio   # weight for length
    w_ang = dominance_ratio     # weight for angle

    # normalize
    w_sum = w_len + w_ang
    w_len /= w_sum
    w_ang /= w_sum

    # --- Rank edges by length ---
    length_ranks = lengths.argsort().argsort()  # 0 = shortest

    scores = []

    #debugging : added scores_i to hold only score vals
    scores_i = []

    for rank, (i, p1, p2, length, ang) in zip(length_ranks, edges):
        length_score = (len(edges) - rank) / len(edges)   # shorter → higher
        angle_score = 1 - (ang / math.pi) # smaller angle → higher    

        score = w_len * length_score + w_ang * angle_score
        scores.append((score, i, p1, p2))
        
        #debugging : append to scores_i
        scores_i.append(score)



    scores.sort(reverse=True, key=lambda x: x[0])
    _, head_idx, p1, p2 = scores[0]


    return _, head_idx, p1, p2


def find_head_tail_from_triangle_weighted(triangle, centroid, direction_deg):
    """
    Determine head edge and tail point using adaptive scoring.

    Method :

    - If triangle is asymmetric → prioritize shortest edge *** (should improve to prioritize shortest/longest edge)
    - If symmetric → prioritize alignment with motion direction 
    - If confidence low → fallback to backward scoring (based on threshold set by distribution analysis)

    Args: 
        triangle (ndarray): Array of shape (3, 2) representing triangle vertex coordinates.
        centroid (ndarray): Array of shape (2,) representing the (x, y) centroid of the contour.
        direction_deg (float): Direction of motion in degrees (from motion tracking).

    Returns:
        head_edge (tuple): (p1, p2)
        tail_point (ndarray): identified tail point
        confidence (float): confidence score
        movement (str): "FORWARD" or "BACKWARD"
    """
    # assume forward movement intially 
    movement = "FORWARD"

    theta = math.radians(direction_deg)
    motion_vec = np.array([math.cos(theta), math.sin(theta)])

    edges = []
    for i in range(3):
        p1 = triangle[i]
        p2 = triangle[(i + 1) % 3]
        length = np.linalg.norm(p2 - p1)
        midpoint = (p1 + p2) / 2
        vec_to_mid = midpoint - centroid
        ang = angle_between(motion_vec, vec_to_mid)
        edges.append((i, p1, p2, length, ang))

    lengths = np.array([e[3] for e in edges])

    angles = np.array([a[4] for a in edges])


    # Compute how dominant the shortest edge is
    shortest = lengths.min()
    mean_other = np.mean(lengths[lengths != shortest]) if np.sum(lengths != shortest) else shortest
    dominance_ratio = shortest / (mean_other * 1.5 + 1e-6)

    # dominance_ratio → 0 means one edge is very small
    # dominance_ratio → 1 means edges similar

    w_len = 1 - dominance_ratio   # weight for length
    w_ang = dominance_ratio     # weight for angle

    # normalize
    w_sum = w_len + w_ang
    w_len /= w_sum
    w_ang /= w_sum

    # Rank edges by length
    length_ranks = lengths.argsort().argsort()  # 0 = shortest

    scores = []

    #debugging : added scores_i to hold only score vals
    scores_i = []

    for rank, (i, p1, p2, length, ang) in zip(length_ranks, edges):
        length_score = (len(edges) - rank) / len(edges)   # shorter → higher
        angle_score = 1 - (ang / math.pi) # smaller angle → higher    

        score = w_len * length_score + w_ang * angle_score
        scores.append((score, i, p1, p2))

        
        #debugging : append to scores_i
        scores_i.append(score)


    scores.sort(reverse=True, key=lambda x: x[0])
    s, head_idx, p1, p2 = scores[0]

    #debugging
    s_return = s

    # Check confidence score against threshold
    if s > 0.8:

        head_edge = (p1, p2)
        tail_idx = (head_idx + 2) % 3
        tail_point = triangle[tail_idx]
    
    # if backwards detected recompute head/tail with opposite motion
    else: 
        s, head_idx, p1, p2 = backwards_score(triangle, centroid, direction_deg)
        movement = "BACKWARD"

        head_edge = (p1, p2)
        tail_idx = (head_idx + 2) % 3
        tail_point = triangle[tail_idx]

    #debugging : sort scores
    scores_i.sort(reverse=True)
    

    #debugging : added s_return to output per frame
    return head_edge, tail_point, s_return, movement


# ----------------------------
# Main tracking function
# ----------------------------

def track_cell(video_path, output_csv, overlay_video, thresh_val=40, min_area=200):
    """
    Main tracking pipeline.

    Steps:
    ------
    1. Load video, get frames and compute background (median frame)
    2. Foreground segmentation via percentile threshold
    3. Extract largest contour per frame
    4. Compute centroid, pose, direction
    5. Detect head/tail if elongated
    6. Save overlay frames and CSV output
    7. Combine overlay frames into video (ffmpeg)

    Outputs:
    --------
    CSV columns:
        frame, x, y, pose, movement, direction_deg, contour
    """

    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    temp_overlay_dir = "overlay_frames_temp"
    os.makedirs(temp_overlay_dir, exist_ok=True)

    frames_gray = []
    for _ in tqdm(range(frame_count), desc="Reading frames"):
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        frames_gray.append(gray.astype(np.uint8))

    frames_gray = np.array(frames_gray)
    background = np.median(frames_gray, axis=0).astype(np.uint8)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    results = []
    pos_history = deque(maxlen=6)
    last_direction = np.nan

    #debugging : added scores_idx to track all scores
    scores_idx = []
    errors = []

    for frame_idx in tqdm(range(frame_count), desc="Tracking"):
        ret, frame = cap.read()
        if not ret:
            break

        gray = frames_gray[frame_idx]
        fg = cv2.absdiff(gray, background)

        t = np.percentile(fg, thresh_val)
        mask = (fg > t).astype(np.uint8) * 255

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        cx = cy = direction = np.nan
        pose = ""
        contour_str = ""
        movement = ""

        #debugging added circ_error and conf_score
        conf = 0
        cerror = 0


        overlay_frame = np.zeros((height, width, 4), dtype=np.uint8)

        if contours:
            contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(contour) > min_area:

                pts = contour.reshape(-1, 2)
                for i in range(len(pts)):
                    p1 = tuple(pts[i].astype(int))
                    p2 = tuple(pts[(i + 1) % len(pts)].astype(int))
                    cv2.line(overlay_frame, p1, p2, (0, 255, 0, 255), 4)

                cx, cy = compute_centroid(contour)
                contour_str = contour_to_string(contour)

                #debbugging added norm error to output
                pose, rect, box, cerror = determine_pose(contour)
                #errors.append(norm_error)



                pos_history.append((cx, cy))
                if len(pos_history) == 6:
                    direction = motion_direction(pos_history[0], pos_history[-1])
                    last_direction = direction
                else:
                    direction = last_direction

                if pose == "CONTRACTED":
                    movement = "UNDEFINED"
                    for i in range(4):
                        cv2.line(overlay_frame,
                                 tuple(box[i].astype(int)),
                                 tuple(box[(i + 1) % 4].astype(int)),
                                 (255, 0, 0, 255), 2)

                else:
                    retval, triangle = cv2.minEnclosingTriangle(contour)
                    triangle = triangle.reshape(3, 2)

                    for i in range(3):
                        cv2.line(overlay_frame,
                                 tuple(triangle[i].astype(int)),
                                 tuple(triangle[(i + 1) % 3].astype(int)),
                                 (0, 255, 255, 255), 2)

                    if not np.isnan(direction):
                        head_edge, tail_point, scores, movement = \
                            find_head_tail_from_triangle_weighted(triangle,
                                                                  np.array([cx, cy]),
                                                                  direction)
                        #debugging
                        conf = scores

                        if head_edge is not None:
                            cv2.line(overlay_frame,
                                     tuple(head_edge[0].astype(int)),
                                     tuple(head_edge[1].astype(int)),
                                     (0, 255, 0, 255), 4)

                        if tail_point is not None:
                            cv2.circle(overlay_frame,
                                       tuple(tail_point.astype(int)),
                                       6, (0, 0, 255, 255), -1)

                        #debugging : appended each frames scores to idx    
                        scores_idx.append(scores)

                cv2.circle(overlay_frame, (int(cx), int(cy)), 4, (255, 0, 0, 255), -1)
                draw_arrow(overlay_frame, (int(cx), int(cy)), direction)

        overlay_path = os.path.join(temp_overlay_dir, f"frame_{frame_idx:05d}.png")
        cv2.imwrite(overlay_path, overlay_frame)

        results.append({
            "frame": frame_idx,
            "x": cx,
            "y": cy,
            "pose": pose,
            "movement": movement,
            #debugging
            #"conf": conf,
            #"circ_error": cerror,
            "direction_deg": direction,
            "contour": contour_str
            
        })
    


    cap.release()
    pd.DataFrame(results).to_csv(output_csv, index=False)
    print(f"Saved CSV → {output_csv}")

    overlay_pattern = os.path.join(temp_overlay_dir, "frame_%05d.png")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-i", overlay_pattern,
        "-filter_complex", "[1]format=rgba[ovr];[0][ovr]overlay",
        "-c:a", "copy",
        overlay_video
    ]
    subprocess.run(cmd, check=True)
    print(f"Saved overlay → {overlay_video}")

    #debugging : print scores
    '''
    for s in scores_idx:
        print(s)
    
    for e in errors:
        print(e)
    '''
# ----------------------------
# CLI
# ----------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--overlay", required=True)
    parser.add_argument("--thresh", type=float, default=40)
    parser.add_argument("--min_area", type=int, default=200)

    args = parser.parse_args()

    track_cell(
        args.video,
        args.output,
        args.overlay,
        args.thresh,
        args.min_area
    )
