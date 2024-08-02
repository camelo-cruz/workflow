# Frequently Asked Questions

This document is a collection of problems and solutions when running the scripts on the Phonetik Server at ZAS

## Python cannot be found

Error message: `Der Befehl "python" ist entweder falsch geschrieben oder konnte nicht gefunden werden`

This problem should not occur anymore, since we installed Python 3.12.4 globally in the folder `C:\Programme\Python312`

You can check which Python file is used via `where python` on the command line

**Note** The Readme instructs you to type in `python3` - but this only works on MacOS and Linux. The Phonetik Server runs on Windows and hence just type `python` instead of `python3`

## Failed to import pytorch fbgemm.dll or one of its dependencies is missing

Sometimes installing the packages as described in the Readme fails. This is probably because of a problem in current versions of some Python package.

Workaround: Use Anaconda instead of Python virtual environments as follows:
* Install [Miniconda](https://docs.anaconda.com/miniconda/) with the recommended options
* Add `C:\Users\<your_user_name>\AppData\Local\miniconda3\Scripts` to your Path environment variable (see below)
* Open a terminal window (`cmd`) 
* Run the command `conda init`
* Close and reopen the cmd shell again
* Run the command `conda create -n workflow`
* Run the command `conda activate workflow`
* Run the command `conda install pytorch torchvision torchaudio pytorch-cuda=12.4 -c pytorch -c nvidia`
* Run the command `conda install -c conda-forge librosa`
* check if PyTorch works:
    * Type `python` to start the Python interpreter
    * type `import torch`
    * if there is no error, you have solved the problem
    * close the interpreter by typing `quit()`
 
Continue with the installation of the other packages required:
* Change into the directory where you checked out this git repo
* Run the command `python -m pip install -r requirments.txt` 


## [WinError 2] Das System kann die angegebene Datei nicht finden 

The error message occurs when running the Python script `automatic_transcription.py`. The script starts processing the first `binaries` folder and stops with the error message that the specified file cannot be found. 

The error message is misleading - the script stops because Whisper cannot find the `ffmpeg.exe` binary.

Solution: Add the path `C:\ffmpeg\bin` to the `Path` environment variable. To do so, click on the Start menu and search for "Umgebungsvariablen". Open the search result "Umgebungsvariablen für dieses Konto bearbeiten", select "Path" in the top part of the screen, click on the Button "Bearbeiten", click on "Neu", click on "Durchsuchen", select the Directory  "Dieser PC" > "System (C:)" > "ffmpeg" > "bin" and close all dialogs by clicking on "OK".

**Note** you need to close the terminal window and start a new one for the Path variable to be updated.



