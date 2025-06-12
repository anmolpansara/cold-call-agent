import streamlit as st
import requests
import json
from datetime import datetime
import pandas as pd
import io

# Configure Streamlit page
st.set_page_config(
    page_title="Cold Call Agent Demo",
    page_icon="📞",
    layout="centered"
)

# Backend API URL
API_BASE_URL = "http://localhost:8000"

def main():
    st.title("📞 Cold Call Agent Demo")
    st.markdown("---")
    
    # Create tabs for different functionalities
    tab1, tab2 = st.tabs(["Single Call", "Bulk Upload (CSV)"])
    
    # Tab 1: Single Call Form
    with tab1:
        with st.form("call_form"):
            st.subheader("Initiate Outbound Call")
            
            # User inputs
            user_name = st.text_input(
                "Customer Name",
                placeholder="Enter customer name (e.g., Jayden)",
                help="Name of the customer to call"
            )
            
            phone_number = st.text_input(
                "Phone Number",
                placeholder="Enter phone number (e.g., +1234567890)",
                help="Customer's phone number with country code"
            )
            
            linkedin_url = st.text_input(
                "LinkedIn URL (Optional)",
                placeholder="https://www.linkedin.com/in/username",
                help="Customer's LinkedIn profile URL for follow-up message"
            )
            
            # Submit button
            submitted = st.form_submit_button(
                "🚀 Make Call",
                type="primary",
                use_container_width=True
            )
            
            if submitted:
                if not user_name or not phone_number:
                    st.error("❌ Please fill in both customer name and phone number")
                else:
                    call_result = initiate_call(user_name, phone_number)
                    
                    # Store LinkedIn URL in session state for potential follow-up
                    if call_result and linkedin_url:
                        if "recent_calls" not in st.session_state:
                            st.session_state.recent_calls = []
                            
                        st.session_state.recent_calls.append({
                            "name": user_name,
                            "phone": phone_number,
                            "linkedin_url": linkedin_url,
                            "call_reference": call_result.get("call_details", {}).get("room_name", "unknown")
                        })
    
    # Tab 2: CSV Upload
    with tab2:
        st.subheader("Upload Contact List (CSV)")
        
        # Instructions for CSV format
        st.info("""
        📝 CSV file should contain at least two columns:
        - **name**: Customer's name
        - **phone**: Phone number with country code
        - **linkedin_url**: (Optional) LinkedIn profile URL for follow-up
        - **industry**: (Optional) Industry of the customer
        
        Example:
        ```
        name,phone,linkedin_url,industry
        John Doe,+1234567890,https://www.linkedin.com/in/johndoe,Software
        Jane Smith,+0987654321,https://www.linkedin.com/in/janesmith,Marketing
        ```
        """)
        
        # File uploader
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        
        if uploaded_file is not None:
            try:
                # Read CSV with phone column explicitly as string type
                df = pd.read_csv(uploaded_file, dtype={'phone': str})
                
                # Convert all phone numbers to strings if they exist
                if 'phone' in df.columns:
                    df['phone'] = df['phone'].astype(str)
                    
                    # Format phone numbers properly - strip any non-digit chars except '+'
                    df['phone'] = df['phone'].apply(lambda x: str(x).strip())
                    # Add '+' prefix if missing
                    df['phone'] = df['phone'].apply(lambda x: '+' + x if not x.startswith('+') else x)
                
                # Validate required columns
                required_cols = ['name', 'phone']
                if not all(col in df.columns for col in required_cols):
                    st.error("❌ CSV must contain 'name' and 'phone' columns")
                else:
                    # Show preview of data
                    st.subheader("Contact Preview")
                    st.dataframe(df, hide_index=True)

                    # Add call approach options
                    call_approach = st.radio(
                        "Select call approach:",
                        ["Call selected contacts now"]
                    )
                    
                    if call_approach == "Call selected contacts now":
                        # Original functionality for immediate calls
                        # Select which contacts to call
                        st.subheader("Select Contacts to Call")
                        
                        # Option for selecting all
                        select_all = st.checkbox("Select All Contacts", value=False)
                        
                        # If select all is checked, select all contacts
                        if select_all:
                            selected_indices = list(range(len(df)))
                        else:
                            # Multiselect for individual contacts
                            options = [f"{row['name']} ({row['phone']})" for _, row in df.iterrows()]
                            selected_options = st.multiselect("Select contacts to call:", options)
                            selected_indices = [options.index(option) for option in selected_options]
                        
                        # Calculate selection counts
                        total_contacts = len(df)
                        selected_count = len(selected_indices)
                        
                        # Display selection info
                        st.text(f"Selected {selected_count} out of {total_contacts} contacts")
                        
                        # Make calls to selected contacts
                        if selected_indices:
                            if st.button("📞 Call Selected Contacts", type="primary", use_container_width=True):
                                call_progress = st.progress(0)
                                status_container = st.container()
                                
                                # Initialize session state for storing call results
                                if "recent_calls" not in st.session_state:
                                    st.session_state.recent_calls = []
                                
                                for i, idx in enumerate(selected_indices):
                                    contact = df.iloc[idx]
                                    contact_name = contact['name']
                                    contact_phone = contact['phone']
                                    contact_linkedin = contact.get('linkedin_url', '') if 'linkedin_url' in df.columns else ''
                                    
                                    status_container.text(f"Calling {contact_name} at {contact_phone}...")
                                    call_result = initiate_call(contact_name, contact_phone)
                                    
                                    # Store call information for potential LinkedIn follow-up
                                    if call_result:
                                        call_reference = call_result.get("call_details", {}).get("room_name", "unknown")
                                        st.session_state.recent_calls.append({
                                            "name": contact_name,
                                            "phone": contact_phone,
                                            "linkedin_url": contact_linkedin,
                                            "call_reference": call_reference
                                        })
                                    
                                    # Update progress
                                    progress = (i + 1) / len(selected_indices)
                                    call_progress.progress(progress)
                                    
                                status_container.success(f"✅ Completed {selected_count} calls")
                    
                    else:  # Schedule calls for entire list
                        st.subheader("Schedule Bulk Calls")
                        
                        # Date and time picker for scheduling
                        col1, col2 = st.columns(2)
                        with col1:
                            scheduled_date = st.date_input("Select Date", datetime.now().date())
                        with col2:
                            scheduled_time = st.time_input("Select Time", datetime.now().time())
                        
                        # Combine date and time
                        scheduled_datetime = datetime.combine(scheduled_date, scheduled_time)
                        
                        total_contacts = len(df)
                        st.text(f"Will schedule calls for all {total_contacts} contacts at {scheduled_datetime}")
                        
                        # Schedule calls button
                        if st.button("📅 Schedule All Calls", type="primary", use_container_width=True):
                            if schedule_bulk_calls(df, scheduled_datetime):
                                st.success(f"✅ Successfully scheduled {total_contacts} calls")
            
            except Exception as e:
                st.error(f"❌ Error processing CSV: {str(e)}")
    
    # LinkedIn Follow-up Section (appears after calls have been made)
    if "recent_calls" in st.session_state and st.session_state.recent_calls:
        st.markdown("---")
        st.header("📱 LinkedIn Follow-up Messages")
        st.markdown("Send follow-up messages to contacts you've called via LinkedIn")

        # Filter only contacts with LinkedIn URLs
        linkedin_contacts = [contact for contact in st.session_state.recent_calls if contact.get("linkedin_url")]
        
        if not linkedin_contacts:
            st.info("No contacts with LinkedIn URLs available for follow-up")
        else:
            # Create a selectbox for choosing a contact
            contact_options = [f"{contact['name']} - {contact['linkedin_url']}" for contact in linkedin_contacts]
            selected_contact_idx = st.selectbox("Select contact for LinkedIn follow-up:", range(len(contact_options)), 
                                              format_func=lambda x: contact_options[x])
            selected_contact = linkedin_contacts[selected_contact_idx]
            
            with st.form("linkedin_form"):
                # Message template with variables
                default_message = f"Hello {{{selected_contact['name']}}},\n\nThank you for our conversation regarding the 2026 Intercontinental Commodity Exchange in Dubai. I'd like to provide some additional information about the event and discuss how you can participate.\n\nLooking forward to connecting further.\n\nBest regards,\nICE Dubai Team"
                
                message_content = st.text_area(
                    "LinkedIn Message",
                    value=default_message,
                    height=200,
                    help="You can use {user_name} as a placeholder for the contact's name"
                )
                
                send_button = st.form_submit_button("📤 Send LinkedIn Message", type="primary", use_container_width=True)
                
                if send_button:
                    result = send_linkedin_followup(
                        selected_contact["linkedin_url"],
                        message_content,
                        selected_contact["call_reference"],
                        selected_contact["name"]
                    )
                    if result and result.get("message"):
                        st.success(f"✅ {result.get('message')}")
                    else:
                        st.error("❌ Failed to send LinkedIn message")

def initiate_call(user_name: str, phone_number: str):
    """
    Send request to backend to initiate the call
    """
    with st.spinner("🔄 Initiating call..."):
        try:
            # Convert phone_number to string to prevent int64 serialization issues
            if not isinstance(phone_number, str):
                phone_number = str(phone_number)
            
            # Ensure phone number has proper format (add + if missing)
            if phone_number and not phone_number.startswith('+'):
                phone_number = '+' + phone_number
                
            # Prepare request payload
            payload = {
                "user_name": user_name,
                "phone_number": phone_number
            }
            
            # Make API request
            response = requests.post(
                f"{API_BASE_URL}/initiate_call",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                st.success(f"✅ Call to {user_name} initiated successfully!")
                
                st.info("💡 The agent will now dial the provided number and attempt to make the cold call.")
                return result
            else:
                error_detail = response.json().get("detail", "Unknown error")
                st.error(f"❌ Failed to initiate call: {error_detail}")
                return None
                
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend. Make sure the FastAPI server is running on port 8000.")
        except requests.exceptions.Timeout:
            st.error("❌ Request timed out. Please try again.")
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
    
    return None

def send_linkedin_followup(linkedin_url, message_content, call_reference, user_name):
    """
    Send a LinkedIn follow-up message
    """
    with st.spinner("📤 Sending LinkedIn message..."):
        try:
            # Prepare request payload
            payload = {
                "linkedin_profile_url": linkedin_url,
                "message_content": message_content,
                "call_reference": call_reference,
                "user_name": user_name
            }
            
            # Make API request
            response = requests.post(
                f"{API_BASE_URL}/send_linkedin_message",
                json=payload,
                timeout=60  # LinkedIn automation might take longer
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_detail = response.json().get("detail", "Unknown error")
                st.error(f"❌ Failed to send LinkedIn message: {error_detail}")
                return None
                
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend. Make sure the FastAPI server is running on port 8000.")
            return None
        except requests.exceptions.Timeout:
            st.error("❌ Request timed out. The LinkedIn automation might still be running in the background.")
            return None
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            return None

def schedule_bulk_calls(df, scheduled_datetime):
    """
    Store scheduled calls locally in session state since backend endpoint doesn't exist yet
    """
    try:
        # Initialize scheduled calls in session state if not exists
        if 'scheduled_calls' not in st.session_state:
            st.session_state.scheduled_calls = []
        
        # Get contact information
        contacts = []
        for _, row in df.iterrows():
            contact_info = {
                "user_name": row['name'],
                "phone_number": row['phone']
            }
            
            # Add LinkedIn URL if available
            if 'linkedin_url' in df.columns and not pd.isna(row['linkedin_url']):
                contact_info["linkedin_url"] = row['linkedin_url']
                
            contacts.append(contact_info)
        
        # Store in session state
        st.session_state.scheduled_calls.append({
            "contacts": contacts,
            "scheduled_datetime": scheduled_datetime,
            "status": "pending"
        })
        
        # Show scheduled call information
        st.info(f"📅 Calls scheduled for {scheduled_datetime.strftime('%Y-%m-%d %H:%M')}")
        st.warning("⚠️ Note: This is a local schedule only. Backend implementation for scheduling is required to make actual calls at the scheduled time.")
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error scheduling calls: {str(e)}")
        return False

# Sidebar with information
with st.sidebar:
    st.header("ℹ️ About")
    st.markdown("""
    This demo showcases an AI-powered outbound calling agent that:
    
    - 📞 Calls customers automatically
    - 🗣️ Uses natural voice conversation
    - 🤝 Presents event details and handles objections
    - 📈 Secures participation for the Dubai Commodity Exchange
    - 📱 Sends LinkedIn follow-up messages
    
    """)
    
    st.header("🛠️ Backend Status")
    try:
        health_response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if health_response.status_code == 200:
            st.success("✅ Backend is running")
        else:
            st.error("❌ Backend error")
    except:
        st.error("❌ Backend not accessible")

if __name__ == "__main__":
    main()