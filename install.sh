#!/bin/bash
# Installation script for Bybit Trading Analysis Agent

echo "🚀 Installing Bybit Trading Analysis Agent..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "⚡ Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your API keys!"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your API keys:"
echo "   - ANTHROPIC_API_KEY"
echo "   - BYBIT_API_KEY"
echo "   - BYBIT_API_SECRET"
echo ""
echo "2. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "3. Run the agent:"
echo "   python -m agent.main analyze --symbol BTC/USDT"
echo "   python -m agent.main monitor --symbol BTC/USDT --interval 300"
echo ""
