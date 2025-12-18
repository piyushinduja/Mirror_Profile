import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from markdown_it import MarkdownIt

# Scopes required for Google Docs and Drive API
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]

# Initialize the Markdown parser
md = MarkdownIt()

def markdown_to_docs_requests(markdown_content, start_index=1):
    """
    Converts a Markdown string into a list of Google Docs batchUpdate requests,
    handling headings (H1, H2), bold text, italic text, and paragraph spacing.
    
    IMPORTANT: Insert all text first, then apply formatting.
    """
    tokens = md.parse(markdown_content)
    requests = []
    formatting_requests = []  # Store formatting to apply AFTER text insertion
    current_index = start_index

    # Prepend a newline if appending (only if start_index > 1)
    if start_index > 1:
        requests.append({
            'insertText': {
                'location': {'index': current_index},
                'text': '\n\n'
            }
        })
        current_index += 2

    # Map for heading levels
    heading_map = {
        1: 'HEADING_1',
        2: 'HEADING_2',
        3: 'HEADING_3'
    }

    # Variable to track heading level
    current_heading_level = None
    
    # --- The main token loop ---
    for i, token in enumerate(tokens):
        
        # --- Handle Headings (H1, H2, etc.) ---
        if token.type == 'heading_open':
            current_heading_level = int(token.tag[1])
        
        elif token.type == 'heading_close':
            current_heading_level = None
        
        # --- Handle Inline Content ---
        elif token.type == 'inline':
            paragraph_start_index = current_index
            
            # Track formatting state
            is_bold = False
            is_italic = False
            
            # Process all children tokens
            if token.children:
                for child in token.children:
                    
                    # Update BOLD flag
                    if child.type == 'strong_open':
                        is_bold = True
                        continue
                    elif child.type == 'strong_close':
                        is_bold = False
                        continue
                    
                    # Update ITALIC flag
                    if child.type == 'em_open':
                        is_italic = True
                        continue
                    elif child.type == 'em_close':
                        is_italic = False
                        continue
                    
                    # Handle softbreak
                    if child.type == 'softbreak':
                        requests.append({
                            'insertText': {
                                'location': {'index': current_index},
                                'text': ' '
                            }
                        })
                        current_index += 1
                        continue

                    # Handle TEXT content
                    if child.type == 'text' and child.content:
                        text_to_insert = child.content
                        text_length = len(text_to_insert)
                        text_start = current_index
                        text_end = current_index + text_length

                        # 1. Insert the text (add to requests immediately)
                        requests.append({
                            'insertText': {
                                'location': {'index': current_index},
                                'text': text_to_insert
                            }
                        })

                        # 2. Store formatting to apply LATER (after all text is inserted)
                        if is_bold or is_italic:
                            text_style = {}
                            fields = []
                            
                            if is_bold:
                                text_style['bold'] = True
                                fields.append('bold')
                            if is_italic:
                                text_style['italic'] = True
                                fields.append('italic')
                            
                            formatting_requests.append({
                                'updateTextStyle': {
                                    'range': {
                                        'startIndex': text_start,
                                        'endIndex': text_end
                                    },
                                    'textStyle': text_style,
                                    'fields': ','.join(fields)
                                }
                            })
                        
                        # Update current index
                        current_index = text_end

            # --- Add newline after inline content ---
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': '\n'
                }
            })
            newline_index = current_index
            current_index += 1

            # --- Store BLOCK-level formatting for later ---
            paragraph_end_index = newline_index  # Don't include the newline in formatting
            
            # Only apply paragraph formatting if there's actual content
            if paragraph_end_index > paragraph_start_index:
                
                # Apply heading style if this was a heading
                if current_heading_level is not None:
                    formatting_requests.append({
                        'updateParagraphStyle': {
                            'range': {
                                'startIndex': paragraph_start_index,
                                'endIndex': paragraph_end_index
                            },
                            'paragraphStyle': {
                                'namedStyleType': heading_map.get(current_heading_level, 'NORMAL_TEXT')
                            },
                            'fields': 'namedStyleType'
                        }
                    })
                
                # Apply paragraph spacing for normal paragraphs
                elif i > 0 and tokens[i-1].type == 'paragraph_open':
                    formatting_requests.append({
                        'updateParagraphStyle': {
                            'range': {
                                'startIndex': paragraph_start_index,
                                'endIndex': paragraph_end_index
                            },
                            'paragraphStyle': {
                                'spaceBelow': {
                                    'magnitude': 10.0,
                                    'unit': 'PT'
                                }
                            },
                            'fields': 'spaceBelow'
                        }
                    })

    # CRITICAL: Return text insertion requests FIRST, then formatting requests
    # Google Docs API processes requests in order, so text must exist before formatting
    return requests + formatting_requests
    

def get_credentials():
    """
    Authenticate and get credentials for Google Docs API.
    Uses Streamlit secrets for deployment or local credentials.json for development.
    """
    # Try Streamlit secrets first (for deployment)
    try:
        if hasattr(st, 'secrets') and "google_credentials" in st.secrets:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["google_credentials"],
                scopes=SCOPES
            )
            return creds
    except Exception as e:
        print(f"Could not load from Streamlit secrets: {e}")
    
    # Fall back to local service account file (for local development)
    if os.path.exists('./credentials.json'):
        creds = service_account.Credentials.from_service_account_file(
            './credentials.json',
            scopes=SCOPES
        )
        return creds
    
    # If neither exists, raise error with helpful message
    raise FileNotFoundError(
        "Credentials not found!\n\n"
        "For Streamlit Cloud deployment:\n"
        "  1. Go to your app settings\n"
        "  2. Click 'Secrets'\n"
        "  3. Add your Google service account JSON as 'google_credentials'\n\n"
        "For local development:\n"
        "  1. Download credentials.json from Google Cloud Console\n"
        "  2. Place it in the same directory as this file\n"
        "  3. Visit: https://console.cloud.google.com/apis/credentials"
    )


def create_google_doc(title, content, folder_id="0AIKRNYJ7JQZnUk9PVA"):
    """
    Create a new Google Doc with the given title and content.
    Documents are created in a shared folder since service accounts 
    don't have their own Drive space.
    
    Args:
        title (str): Title of the document
        content (str): Content to add to the document
        folder_id (str): Google Drive folder ID (REQUIRED for service accounts)
    
    Returns:
        dict: Dictionary containing document_id and document_url
    """
    try:
        # Get credentials
        creds = get_credentials()
        
        # Build the Drive and Docs API services
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        
        # Create document metadata with parent folder
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document',
            'parents': [folder_id]
        }
        
        # Create the document using Drive API (in the specified folder)
        file = drive_service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        document_id = file.get('id')
        
        # # Now add content using Docs API
        # requests = [
        #     {
        #         'insertText': {
        #             'location': {
        #                 'index': 1,
        #             },
        #             'text': content
        #         }
        #     }
        # ]

        # # Execute the batch update
        # docs_service.documents().batchUpdate(
        #     documentId=document_id,
        #     body={'requests': requests}
        # ).execute()
    
        # --- CHANGE HERE: Use the converter function ---
        # The initial index for a brand new document is 1
        requests = markdown_to_docs_requests(content, start_index=1)
        
        # Execute the batch update
        if requests: # Only execute if there are requests to make
            docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()
            
        document_url = f'https://docs.google.com/document/d/{document_id}/edit'
        
        return {
            'document_id': document_id,
            'document_url': document_url,
            'success': True,
            'message': 'Document created successfully!'
        }
    
    except FileNotFoundError as e:
        return {
            'success': False,
            'message': str(e)
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error creating document: {str(e)}'
        }


def append_to_google_doc(document_id, content):
    """
    Append content to an existing Google Doc.
    
    Args:
        document_id (str): ID of the document to append to
        content (str): Content to append
    
    Returns:
        dict: Status dictionary
    """
    try:
        # Get credentials
        creds = get_credentials()
        
        # Build the Docs API service
        service = build('docs', 'v1', credentials=creds)
        
        # # Get the current document to find the end index
        # doc = service.documents().get(documentId=document_id).execute()
        # end_index = doc.get('body').get('content')[-1].get('endIndex') - 1
        
        # # Prepare request to append content
        # requests = [
        #     {
        #         'insertText': {
        #             'location': {
        #                 'index': end_index,
        #             },
        #             'text': '\n\n' + content
        #         }
        #     }
        # ]
        
        # # Execute the batch update
        # service.documents().batchUpdate(
        #     documentId=document_id,
        #     body={'requests': requests}
        # ).execute()

        doc = service.documents().get(documentId=document_id).execute()
        # end_index is the last index *before* the trailing newline
        end_index = doc.get('body').get('content')[-1].get('endIndex') - 1
        
        # --- CHANGE HERE: Use the converter function ---
        # The starting index is the end of the current document content
        # Note: markdown_to_docs_requests now handles the necessary leading newlines.
        requests = markdown_to_docs_requests(content, start_index=end_index)
        
        # Execute the batch update
        if requests: # Only execute if there are requests to make
            service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()
        
        return {
            'success': True,
            'message': 'Content appended successfully!'
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f'Error appending to document: {str(e)}'
        }
