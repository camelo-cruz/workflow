# Setup Guide

## Prerequisites

- **Python**: Version `3.11.0` (required for compatibility with the installed PyTorch version and CUDA usage) 
- **Conda**: For environment management (recommended)

## Configuration

### Environment Variables

Create a `.env` file in the `backend/materials/` directory to store your API keys and configuration secrets.

> ⚠️ **Important**: Without this file, OneDrive integration will not be available nor using of some models for transcription and translation.

### Required `.env` File Contents

```env
# Hugging Face API Key
# Get your key from: https://huggingface.co/settings/tokens
HUGGING_KEY=your_huggingface_api_key_here

# OneDrive Integration
# Register an app in Azure Portal and obtain these credentials
TENANT_ID=your_azure_tenant_id_here
CLIENT_ID=your_azure_client_id_here
CLIENT_SECRET=your_azure_client_secret_here

# Optional: DeepL Translation API
# Sign up at: https://www.deepl.com/pro-api
DEEPL_API_KEY=your_deepl_api_key_here
```

## Installation & Deployment Options

### Option 1: ZAS Organization Members

If you're part of ZAS:

1. Contact your system administrator for server connection details
2. Follow the specific connection instructions provided by your administrator

> 🔒 **Security Note**: Server paths are not included in this documentation for security reasons.

### Option 2: Docker Deployment

For containerized deployment:

1. Obtain the Docker command from your code administrator
2. Run the provided Docker command
3. Set up Watchtower for automatic updates:

```bash
# Example Watchtower setup for auto-updates
docker run -d \
  --name watchtower \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower
```

### Option 3: Local Development Setup

For local development or custom server deployment:

#### 1. Create Conda Environment

```bash
# Create environment from configuration file
conda env create -f environment.yml -n tgt

# Activate the environment
conda activate tgt
```

#### 2. Start the Application

Deploy frontend `dist` by running inside the `frontend` folder:

```bash
npm install
npm run build
```

Then, navigate to the `backend` directory and run:

```bash
# Start the FastAPI server
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

The application will be available at: `http://127.0.0.1:8000`

## Important Notes

### Security Best Practices

- 🚫 **Never commit your `.env` file to version control**
- 🔐 Keep all API keys and secrets private
- 📁 Ensure the `.env` file has proper file permissions (readable only by the application user)

### Optional Features

- **DeepL Translation**: If you don't plan to use DeepL API, you can skip adding the `DEEPL_API_KEY` or modify the translation factory to remove the DeepL strategy
- **OneDrive Integration**: Requires all Azure-related environment variables to be properly configured.

If OneDrive is used, be sure to:
- Add the correct paths for authentication in Azure.
- Give full permissions to users.

### Troubleshooting

- Verify Python version: `python --version`
- Check if all required packages are installed: `conda list`
- Ensure the `.env` file is in the correct location: `backend/materials/.env`
- Validate API keys are correctly formatted and have necessary permissions

## Getting API Keys

| Service | How to Get API Key |
|---------|-------------------|
| **Hugging Face** | 1. Create account at [huggingface.co](https://huggingface.co)<br>2. Go to Settings > Access Tokens<br>3. Create new token |
| **Azure/OneDrive** | 1. Go to [Azure Portal](https://portal.azure.com)<br>2. Register new application<br>3. Note down Tenant ID, Client ID, and Client Secret |
| **DeepL** | 1. Sign up at [DeepL Pro](https://www.deepl.com/pro-api)<br>2. Get API key from account dashboard |

## Support

For additional help:
- Contact your system administrator camelo.cruz@leibniz-zas.de
- Check the application logs for error details
- Verify all environment variables are correctly set