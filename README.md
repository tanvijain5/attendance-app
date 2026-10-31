# Attendance App — Professional UI

This package keeps the existing Flask routes and database logic and refreshes the frontend (HTML/CSS/JavaScript).

## Run on Windows
1. Extract this ZIP to a NEW folder, for example `Desktop\Attendance-App-Professional`.
2. In VS Code, choose **File → Open Folder** and open the extracted `Attendance-App-Professional` folder — the one that directly contains `app.py`, `static`, and `templates`.
3. Open a terminal in that folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

4. Open http://127.0.0.1:5000/ in your browser.

The database file is intentionally not included so your original attendance records are not copied or overwritten. On first run, the app creates a new empty `attendance.db`. Use this copy for testing. Do not push real student data or secret keys to GitHub.

## Important
- This package does not change the Flask backend routes.
- JavaScript adds table search and a confirmation prompt before ending a session.
- The landing page and shared CSS have been updated.
- Test login, registration, QR generation, attendance marking, and summaries before replacing your existing GitHub version.
