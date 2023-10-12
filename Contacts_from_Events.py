from nylas import APIClient
import os
import datetime
from dotenv import load_dotenv

# Load your env variables
load_dotenv()

def initialize_nylas():
    # Initialize your Nylas API client
    nylas = APIClient(
        os.environ.get("CLIENT_ID"),
        os.environ.get("CLIENT_SECRET"),
        os.environ.get("ACCESS_TOKEN"),
    )
    
    return nylas
    
# Accepts: A nylas client object and list of Events from the Nylas Calendar API.
# Returns: A list of all Events in which the user is a participant.
def get_user_events(nylas, events):
    # Find the events where the user is a participant.
    user_email = nylas.account.email_address
    user_events = []
    for event in events:
        # Get a list of all participants for the Event.
        participants = [participant["email"] for participant in event["participants"]]
        # If the user is one of the participants, add this Event to the list that's returned.
        if user_email in participants:
            user_events += [event]
    return user_events

# Accepts: A nylas client object and list of Events from the Nylas Calendar API.
# Returns: A list of email addresses for the prospects that are participating in the Events.
def get_prospect_emails(nylas, events):
    prospect_emails = []
    user_email = nylas.account.email_address
    internal_domain = "my_company.com"
    for event in events:
        participants = [participant["email"] for participant in event["participants"]]
        if user_email in participants:
            prospect_emails += [participant for participant in participants if internal_domain not in participant and participant not in prospect_emails]
    return prospect_emails

# Accepts: A nylas client object and a list of prospect emails.
# Returns: A list of Nylas Contact objects.
def get_contact_info(nylas, emails):
    contacts = []
    for email in emails:
        contact = nylas.contacts.where(email=email).first()
        if contact:
            contacts += [contact]
    return contacts

# Accepts: A nylas client object, a prospect email, and a list of Nylas Event objects.
# Returns: Boolean that indicates if user has sent an email to the prospect since their latest meeting.
def has_follow_up(nylas, email, events):
    # Get the most recent email the user sent to the prospect.
    most_recent_sent_message = nylas.messages.where(in_="Sent", to=email, limit=1).first()
    # Assign the message date to a variable we'll use later.
    try:
        last_comm_time = most_recent_sent_message.date
    except AttributeError:
        # If the user has never sent an email to the prospect, set this value to 0.
        last_comm_time = 0
    prospect_meetings = []
    # Check all event participants for the prospect email address.
    for event in events:
        participants = [participant["email"] for participant in event["participants"]]
        if email in participants:
            prospect_meetings.append(event)
    if prospect_meetings:
        # Find the last meeting the prospect was a participant in.
        last_meeting = prospect_meetings[len(prospect_meetings)-1]
        last_meeting_time = last_meeting.when['end_time']
    # If the last meeting timestamp is larger than the last communication time, it means our user
    #   hasn't yet followed up.
    if last_meeting_time > last_comm_time:
        print("You need to follow up with {}".format(email))
        return False
    else:
        print("{} has been followed up with!".format(email))
        return True
      
      
# Accepts: A Nylas client and a prospect's email address.
# Returns: Nothing. It creates an email and sends it.
def draft_email(nylas, email):
    draft = nylas.drafts.create()
    draft.to = [{'email': email}]
    draft.subject = "Following up on our discussion earlier"
    draft.body = "Just wanted to say hi and find out if there is anything I can do to help."
    draft.from_ = [{'email': 'you@example.com', 'name': 'Your Name'}]
    draft.save()
    draft.send()
    
# Accepts: A Nylas client object and an email address.
# Returns: Boolean that indicates if the user has sent an email to the address within the specified timespan.
def is_stale(nylas, email):
    # Find the last email the user sent to the provided email address.
    last_message = nylas.messages.where(in_="Sent", to=email, limit=1).first()
    # Define the period of time we want the user to respond after.
    follow_up_period = int((datetime.date.today() + datetime.timedelta(days=-29)).strftime("%s"))
    
    # If follow_up_period is smaller than the date for the last message, it means an email has been
    #   sent within this period, and the user doesn't need to respond.
    if follow_up_period < last_message.date:
        last_message_pretty = datetime.datetime.fromtimestamp(last_message.date).strftime("%B %d, %Y")
        print("Last communication to {} was on {}".format(email, last_message_pretty))
        return False
    else:
        print("You need to follow up with {}".format(email))
        return True
      
def mark_stale(nylas, email):
    contact = get_contact_info(nylas, [email])[0]
    contact.notes = "Status: Stale"
    print(contact)
    contact.save()
    
def main():
    nylas = initialize_nylas()   
    today = datetime.date.today()  
    # Get a datetime for Monday and Friday of this week.
    monday = today + datetime.timedelta(days=-today.weekday(), weeks=0)
    friday = monday + datetime.timedelta(days=5)  
    # Get the last week.
    past_week_start = today + datetime.timedelta(days=-7)
    # Define the time range for 30-36 days ago.
    distant_start_time = today + datetime.timedelta(days=-36)
    distant_end_time = today + datetime.timedelta(days=-30)
    
    # Request all Calendars the user has access to.
    calendars = nylas.calendars.all()
    # Get the calendar_id of the Calendar named "Prospect Meetings".
    calendar_id = [ calendar['id'] for calendar in calendars if 'alvaro.t@nylas.com' in calendar['name'] ][0]
    
    # Return all Events between this Monday and Friday
    all_upcoming_events = nylas.events.where(
        calendar_id=calendar_id,
        starts_after=monday.strftime("%s"),
        ends_before=friday.strftime("%s")
    )
    # Return all Events in the last week.
    all_past_events = nylas.events.where(
        calendar_id=calendar_id,
        starts_after=past_week_start.strftime("%s"),
        ends_before=today.strftime("%s")
    )
    # Return all Events 31-37 days ago.
    all_distant_events = nylas.events.where(
        calendar_id=calendar_id,
        starts_after=distant_start_time.strftime("%s"),
        ends_before=distant_end_time.strftime("%s")
    )
    
    # ----------------------- Upcoming Meetings Panel
    user_upcoming_events = get_user_events(nylas, all_upcoming_events)
    upcoming_prospect_emails = get_prospect_emails(nylas, user_upcoming_events)
    upcoming_prospect_info = get_contact_info(nylas, upcoming_prospect_emails)
    for email in upcoming_prospect_emails:
        last_message = nylas.messages.where(in_="Sent", to=email, limit=1).first()
        if last_message:
            print("The most recent message sent to {} was on {}".format(
                email,
                datetime.datetime.fromtimestamp(last_message["date"]).strftime("%B %d, %Y - %H:%M:%S")
            ))
        else:
            print("No communications with {}".format(email))
            
     # ----------------------- Past Meetings Panel
    user_past_events = get_user_events(nylas, all_past_events)
    past_prospect_emails = get_prospect_emails(nylas, all_past_events)
    past_prospect_info = get_contact_info(nylas, past_prospect_emails)
    for email in past_prospect_emails:
        if not has_follow_up(nylas, email, user_past_events):
            print("Drafting an email to {}!".format(email))
            draft_email(nylas, email)
            
    # ----------------------- Prospect Reconnect Panel
    user_distant_events = get_user_events(nylas, all_distant_events)
    distant_prospect_emails = get_prospect_emails(nylas, all_distant_events)
    distant_prospect_info = get_contact_info(nylas, distant_prospect_emails)
    for email in past_prospect_emails:
        if is_stale(nylas, email):
            mark_stale(nylas, email);
            
if __name__ == "__main__":
    main()
