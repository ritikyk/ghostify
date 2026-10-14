# Ghostify File Browser

Remote visual dark-mode file browser. Access any PC's files from anywhere.

## Quick Setup (3 commands)

```bash
git clone https://github.com/Simpoolify/ghostify-browser.git
cd ghostify-browser
pip install -r requirements.txt
```

Then edit `file_browser.py` — fill in CONFIG at the top:

| Setting | What to put |
|---|---|
| `PASSWORD` | Your chosen password |
| `DISCORD_WEBHOOK` | Your Discord webhook URL |
| `NGROK_AUTHTOKEN` | Free token from [ngrok.com](https://ngrok.com) |
| `ROOT_DIR` | Folder to browse (`C:\` for full drive) |

Then run:
```bash
python file_browser.py        # start server
python install_startup.py     # make it survive reboots
```

## Features
- Dark-mode visual file browser
- Navigate any folder tree
- Download any file
- Filter/sort files live
- Password protected
- ngrok tunnel = access from any device worldwide
- Posts URL to Discord on every start
