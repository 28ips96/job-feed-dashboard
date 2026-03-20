#!/bin/bash
# setup.sh — Job Feed v3 Fresh Mac Setup
# Run this once on a clean machine.

set -e

echo "🔧 Job Feed v3 — Fresh Setup"
echo "────────────────────────────"

# ─── 1. Check Python ─────────────────────────────────────────────────────────
echo ""
echo "Step 1: Checking Python..."

if command -v python3 &>/dev/null; then
    PY=$(command -v python3)
    PY_VER=$($PY --version 2>&1)
    echo "  ✓ Found $PY_VER at $PY"
else
    echo "  ✗ Python 3 not found."
    echo "    Install from https://www.python.org/downloads/ or:"
    echo "    brew install python3"
    exit 1
fi

# ─── 2. Install dependencies ─────────────────────────────────────────────────
echo ""
echo "Step 2: Installing Python packages..."

$PY -m pip install --upgrade pip --quiet
$PY -m pip install \
    requests \
    openpyxl \
    flask \
    google-auth \
    google-auth-oauthlib \
    google-api-python-client \
    --quiet

echo "  ✓ All packages installed"

# ─── 3. Create directory structure ───────────────────────────────────────────
echo ""
echo "Step 3: Setting up directories..."

FEED_DIR="$HOME/job_feed"
mkdir -p "$FEED_DIR/daily_outputs"

# Copy all Python files to ~/job_feed
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for f in config.py filters.py fetchers.py scorer.py db.py \
         job_feed.py build_excel_v3.py send_email.py dashboard.py run_job_feed.sh; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        cp "$SCRIPT_DIR/$f" "$FEED_DIR/$f"
        echo "  ✓ Copied $f"
    else
        echo "  ⚠️  $f not found in $SCRIPT_DIR"
    fi
done

chmod +x "$FEED_DIR/run_job_feed.sh"

echo "  ✓ Files deployed to $FEED_DIR"

# ─── 4. Fix Python path in run_job_feed.sh ───────────────────────────────────
echo ""
echo "Step 4: Configuring Python path..."

# Detect actual python3 location and update the shell script
PY_PATH=$(command -v python3)
sed -i '' "s|^PYTHON=.*|PYTHON=$PY_PATH|" "$FEED_DIR/run_job_feed.sh"
echo "  ✓ Set PYTHON=$PY_PATH in run_job_feed.sh"

# ─── 5. Gmail OAuth setup ────────────────────────────────────────────────────
echo ""
echo "Step 5: Gmail OAuth setup..."

if [ -f "$FEED_DIR/credentials.json" ]; then
    echo "  ✓ credentials.json already exists"
else
    echo "  ⚠️  credentials.json not found."
    echo ""
    echo "  You need to set this up:"
    echo "  1. Go to https://console.cloud.google.com/apis/credentials"
    echo "  2. Create an OAuth 2.0 Client ID (Desktop app)"
    echo "  3. Download the JSON and save it as:"
    echo "     $FEED_DIR/credentials.json"
    echo ""
    echo "  Then run:  cd $FEED_DIR && python3 send_email.py test test"
    echo "  This will open a browser for OAuth consent (one-time)."
    echo ""
    read -p "  Press Enter after you've placed credentials.json, or Ctrl+C to do it later... "
fi

# ─── 6. Initialize database ──────────────────────────────────────────────────
echo ""
echo "Step 6: Initializing database..."

cd "$FEED_DIR"

# Check if there's a v2 seen_jobs.json to migrate
if [ -f "$FEED_DIR/seen_jobs.json" ]; then
    echo "  Found v2 data, migrating..."
    $PY job_feed.py --migrate
else
    echo "  Fresh install, creating empty database..."
    $PY -c "from db import init_db; init_db(); print('  ✓ Database created')"
fi

# ─── 7. Optional: keyword clusters ───────────────────────────────────────────
echo ""
echo "Step 7: Keyword clusters..."

if [ -f "$FEED_DIR/jd_keywords.json" ]; then
    echo "  ✓ Custom keyword clusters found"
else
    echo "  ℹ️  No custom jd_keywords.json found."
    echo "     The scorer will use built-in defaults (188 keywords, 10 clusters)."
    echo "     To use your 570-keyword file, save it as:"
    echo "     $FEED_DIR/jd_keywords.json"
fi

# ─── 8. Test run ─────────────────────────────────────────────────────────────
echo ""
echo "Step 8: Test run..."
read -p "  Run a test fetch now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  Running job_feed.py..."
    cd "$FEED_DIR"
    $PY job_feed.py
    echo ""
    $PY job_feed.py --stats
fi

# ─── 9. Install launchd agent ────────────────────────────────────────────────
echo ""
echo "Step 9: Setting up daily schedule..."

PLIST_NAME="com.ipshitadeb.jobfeed.plist"
PLIST_SRC="$FEED_DIR/$PLIST_NAME"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
PLIST_DST="$LAUNCH_DIR/$PLIST_NAME"

# Update the plist with correct paths
cat > "$PLIST_SRC" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ipshitadeb.jobfeed</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$FEED_DIR/run_job_feed.sh</string>
    </array>

    <!-- 8:00am EST = 13:00 UTC -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>13</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>$FEED_DIR/feed.log</string>
    <key>StandardErrorPath</key>
    <string>$FEED_DIR/feed.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST

mkdir -p "$LAUNCH_DIR"

# Unload old version if exists
launchctl unload "$PLIST_DST" 2>/dev/null || true

cp "$PLIST_SRC" "$PLIST_DST"
launchctl load "$PLIST_DST"

echo "  ✓ Scheduled: daily at 8:00am EST"
echo "  ✓ Plist: $PLIST_DST"

# ─── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════"
echo "✅ Job Feed v3 setup complete!"
echo ""
echo "Files:     $FEED_DIR/"
echo "Database:  $FEED_DIR/job_feed.db"
echo "Excel:     $FEED_DIR/daily_outputs/"
echo "Log:       $FEED_DIR/feed.log"
echo ""
echo "Commands:"
echo "  python3 $FEED_DIR/job_feed.py           # Manual run"
echo "  python3 $FEED_DIR/job_feed.py --stats   # View stats"
echo "  python3 $FEED_DIR/job_feed.py --rescore # Re-score with new keywords"
echo "  python3 $FEED_DIR/dashboard.py          # Open dashboard at localhost:5050"
echo "════════════════════════════════════"
