# Download Marian weights from OPUS site (not from Hugging Face)
wget https://object.pouta.csc.fi/OPUS-MT-models/pt-en/latest.zip
unzip latest.zip -d pt-en

# Install conversion tools
pip install transformers sentencepiece gitpython

# Convert to Hugging Face format
python src/transformers/models/marian/convert_marian_to_pytorch.py \
  --src pt-en \
  --dest converted