#!/bin/sh

mkdir -p ~/.streamlit/

cat <<EOF > ~/.streamlit/config.toml
[server]
headless = true
enableCORS = false
enableXsrfProtection = false
port = $PORT
address = "0.0.0.0"

[browser]
gatherUsageStats = false
EOF
