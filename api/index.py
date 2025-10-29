# Simple Vercel handler that imports and exports the Flask app
# Vercel's @vercel/python can handle Flask apps directly
from app import app

# Export the app for Vercel
# The vercel.json routing will handle requests to this file
# For direct Flask app support, we can also export it as handler
handler = app
