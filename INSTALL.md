# Installation Guide for Scanly

## Prerequisites

- Python 3.6 or higher
- Git (for cloning the repository)

## Method 1: Standard Installation

### Step 1: Clone the repository
```bash
git clone https://github.com/amcgready/Scanly.git
cd Scanly
```

### Step 2: Create a virtual environment (recommended)
```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy the template configuration file and edit it with your settings:
```bash
cp .env.template .env
```

Open the `.env` file and set your TMDB API key and other configuration options.

### Step 5: Start Scanly
You can start both the main application and web UI using our launcher script:
```bash
python src/main.py
```

## Method 2: Installation from PyPI (Coming Soon)
```bash
pip install scanly
```

## Method 3: Docker Installation

### Step 1: Create a docker-compose file
Use the provided `docker-compose.yml` file or create your own.

### Step 2: Configure environment variables
Create a `.env` file as described in Step 4 above.

### Step 3: Start the Docker container
```bash
docker-compose up -d
```

## Troubleshooting

### Common Issues

1. **TMDB API Key errors**
   Make sure you've set a valid TMDB API key in your `.env` file.

2. **Permission issues**
   Ensure that the application has appropriate permissions to read/write to your media directories.

### Getting Help
If you encounter any issues, please check the logs in the `logs` directory or open an issue on GitHub.