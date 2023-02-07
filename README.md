# jelitto-image-finder
This project was created for a friend to explore getting plant data with Python. It tries to add url to an image for each plant in the Jelitto spreadsheet from the Jelitto site, or from wikimedia commons if Jelitto doesn't have an image.

Interact with the notebook in [Binder](https://mybinder.org/v2/gh/ann-cooper/jelitto-image-finder/master?urlpath=https%3A%2F%2Fgithub.com%2Fann-cooper%2Fjelitto-image-finder%2Fblob%2Fmaster%2Fjelitto_image_finder.ipynb)

To run locally:
- Clone the project & cd into the project directory.
- Run `bash create_venv.sh` to create a virtual environment.
- Activate the venv `source venv/bin/activate`
- Then to open and interact with the notebook, run `jupyter notebook`
- To deactivate the venv: `deactivate`

## Managing dependencies
- Dependencies are managed with pip-tools.
- To update or change dependencies: activate the venv, then install pip-tools with `pip install pip-tools`
- Adjust the packages listed in requirements/main.in as needed.
- To re-output the main.txt: `pip-compile requirements/main.in --output-file=- > requirements/main.txt`
- To install the packages in your venv: `pip install -r requirements/main.txt`

