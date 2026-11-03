# Firebase Service Account Credentials Directory

Place your Firebase Admin SDK service account JSON file here:

Recommended file name:
`backend/config/firebase-service-account.json`
or
`backend/serviceAccountKey.json`

This directory and all `*.json` files within it are ignored by Git via `.gitignore` to prevent leaking credentials.

## How to Obtain Your Firebase Service Account Key
1. Go to the [Firebase Console](https://console.firebase.google.com/).
2. Select your project.
3. Click the gear icon (⚙️) next to Project Overview -> **Project settings**.
4. Navigate to the **Service accounts** tab.
5. Under Firebase Admin SDK, click **Generate new private key**.
6. Save the downloaded JSON file into this folder as:
   `firebase-service-account.json`
7. In your `backend/.env` file, ensure:
   `FIREBASE_CREDENTIALS_PATH=config/firebase-service-account.json`

