// ====================================================================
// stentor_preprocess.ijm
// Fiji macro for Stentor preprocessing
// Input: seq = path to folder containing frames (frame_00001.png ...)
// ====================================================================

// Prompt the user to select a folder
dir = getDirectory("Choose a folder containing your images");

// Open the first image (optional, mainly to help naming)
open(dir + "frame0001.png");

// Load the rest of the images as a sequence
run("Image Sequence...", "open=[" + dir + "] sort");

origID = getImageID();

// Convert to 8-bit
run("8-bit");
rename("frames");

// --- Create average intensity projection ---
run("Z Project...", "projection=[Median]");
rename("MED");


// --- Subtract background ---
imageCalculator("Subtract create stack", "frames", "MED");
rename("SUBTRACTED");

// --- Run TrackMate ---
selectWindow("SUBTRACTED");
run("TrackMate");

// Detector settings baseline
setOption("BlackBackground", false);

// --- Pause for manual TrackMate detector configuration ---
print("\n*** PAUSED: Adjust detector thresholds, then click 'Run' in TrackMate. ***");
waitForUser("Run TrackMate with Manual Settings\nSave csv and close TrackMate windows\nThen click OK here.");



// -------------------------------------------------------------------
// SECOND subtraction
// -------------------------------------------------------------------
selectWindow("MED");


// --- Subtract background ---
imageCalculator("Subtract create stack", "frames", "MED");
rename("SUB2");

// Set black background
setOption("BlackBackground", true);

// Apply Otsu threshold per slice
setAutoThreshold("Otsu dark");

// Convert to binary (Make Binary equivalent)
run("Convert to Mask", "stack");

run("Invert")

// --- Pause for mask saving ---
waitForUser("Save the binary mask now.\nClick OK to finish.");

// --- Cleanup ---
while (nImages > 0) {
    selectImage(nImages);
    close();
}

