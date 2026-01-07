#!/bin/bash
# runs the main pipeline with the official test set
export INPUT_DATA="Dataset/test.csv" 
echo "Starting full inference on $INPUT_DATA..."
echo "This may take a while depending on your hardware."
./venv/bin/python3 main.py 2>&1 | tee pipeline.log
echo "Inference complete. Check results.csv."
