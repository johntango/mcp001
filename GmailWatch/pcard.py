'''
Gmail Pcard Folder Notifier

This script monitors your Gmail label 'Pcard' for new messages and prints a notification
with the sender and subject.

Prerequisites:
1. Enable the Gmail API in Google Cloud Console.
2. Download `credentials.json` and place it alongside this script.
3. Install dependencies:
   pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

Usage:
   python gmail_pcard_notifier.py

'''  
from __future__ import print_function
import os.path
import pickle
import time
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these SCOPES, delete any existing token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
LABEL_NAME = 'test'
POLL_INTERVAL = 60  # seconds between checks


def get_service():
    """Authenticate and return a Gmail API service instance."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no valid credentials, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)


def get_label_id(service, label_name):
    """Retrieve the Gmail label ID for a given label name."""
    labels = service.users().labels().list(userId='me').execute().get('labels', [])
    for label in labels:
        if label['name'] == label_name:
            return label['id']
    raise ValueError(f"Label '{label_name}' not found.")


def watch_for_new_messages(service, label_id, last_history_id=None):
    """Poll history to find new messages under the given label."""
    if last_history_id:
        history = service.users().history().list(
            userId='me', startHistoryId=last_history_id,
            historyTypes=['messageAdded'], labelId=label_id
        ).execute()
        new_msgs = []
        for record in history.get('history', []):
            for added in record.get('messagesAdded', []):
                new_msgs.append(added['message'])
        return new_msgs, history.get('historyId')
    else:
        # First run: fetch existing messages to initialize state.
        result = service.users().messages().list(
            userId='me', labelIds=[label_id]
        ).execute()
        return result.get('messages', []), None


def main():
    service = get_service()
    label_id = get_label_id(service, LABEL_NAME)
    print(f"Monitoring Gmail label '{LABEL_NAME}' for new messages...")

    # Initialize seen set and history ID
    existing, history_id = watch_for_new_messages(service, label_id)
    seen_ids = {msg['id'] for msg in existing}
    # Get current historyId to start incremental watch
    profile = service.users().getProfile(userId='me').execute()
    history_id = profile.get('historyId')

    while True:
        time.sleep(POLL_INTERVAL)
        new_messages, history_id = watch_for_new_messages(service, label_id, history_id)
        for msg in new_messages:
            msg_id = msg['id']
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                # Fetch headers
                msg_detail = service.users().messages().get(
                    userId='me', id=msg_id, format='metadata',
                    metadataHeaders=['From', 'Subject']
                ).execute()
                headers = {h['name']: h['value'] for h in msg_detail['payload']['headers']}
                print(f"New email from {headers.get('From')}: {headers.get('Subject')}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")
