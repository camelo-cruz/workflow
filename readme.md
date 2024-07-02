# Instructions to use scripts


## Download Github and clone repository:

### 1. Download the Github app

[Github app](https://desktop.github.com/download/)

### 2. Clone the repository using the following link:

![Github app](images/github_app.png "app")

Choose from url and copy the following path:

![from url](images/from_url.png "url")

```
https://github.com/camelo-cruz/workflow.git
```


## Create environment :

:exclamation: Be sure you are in the right folder, finishing with workflow :exclamation:

Open the terminal or cmd in your computer. Look for the following program in your computer and open it:

```
cmd
```


Go to the folder of the github repository. If you don't know how to do that, go to cmd and run the following command:

```
dir /S /B /AD "C:\Users\%USERNAME%\workflow"
```

For making sure of that you are in the correct directory, run the following command:

```
pwd
```

the ouput shoul be finishing with workflow. Like here:

![path](images/workflow_path.png "path")

> <strong>Note:</strong> Ignore this step if you have already created an environment

```
python3 -m venv .venv
```
	
## 1. Activate environment:


```
.venv\Scripts\activate
```

##  install requirements:

> **Note:** Ignore this step if you have already created an environment

```
pip install -r requirements.txt
```

## 2. Run the script

- **For automatic transcription**
    - **Replace (main\_folder\_path)** for the path to the parent folder containing the sessions folders
    - **Replace (language)** to the language to transcribe. For example: german, ukranian

```
python source/automatic_transcription.py (main_folder_path) (language)
```

This is an example:

![path](images/transcription_example.png "path")


- **For automatic translation**


    - **Replace (main\_folder\_path)** for the path to the parent folder containing the sessions folders
    - **Replace (language)** to the language from which you want to translate. For example: german, ukranian

```
python source/automatic_translation.py (main_folder_path) (language)
```

- **For automatic glossing**