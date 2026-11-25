# Weekly Health Tracker

Track calories, protein, steps and weight by week (Sunday to Saturday), with weekly targets, suggestions, BMI and an 8-week trend.

## Use it

- **Online / on your phone:** open the GitHub Pages link for this repository. On a phone, add it to your home screen so it opens like an app.
- **On a computer:** open `index.html` in any browser.

Entries are saved automatically in the browser on the device you use (localStorage). They are not uploaded to GitHub. Use **Export backup** / **Import backup** in *Profile & data* to move data between devices.

## Optional: save to a SQL database

With Python installed, run this in this folder and open http://127.0.0.1:8000:

```
python server.py
```

Entries are then also saved to `health.db` (SQLite) next to the script. This only works on your own computer, not on GitHub Pages.
