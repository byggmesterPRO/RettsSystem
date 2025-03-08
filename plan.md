### Information
- This is a court bot for an RP game, but that shouldn't come to light in the commands or text as we pretend everything is real
- It is written in Python using the discord.py library
- All verbose text should be in Norwegian as it's a Norwegian RP game


### Functionality
- The court bot is basically a ticket bot
- It will have channels where there is a message with a button open a ticket, this will open a ticket in a category defined by the command
- `/ticket <category> <title> <description> <button-emoji> <button-text> <role>` - Creates a ticket in the category specified with the given title, description, button emoji and button text 
I think that the bot should have it where it opens a ticket, and then a judge can type /claim to claim the ticket.
A judge will have their own "quarters" which is a category, when a judge claims a ticket the ticket will be moved to the judge's category

### Database Structure
- SQL database (.db file) for storing all information
- Tables for:
  - Tickets/Cases
  - Judges
  - Categories
  - Scheduled notifications
  - Case archives
  - Evidence records

### User Roles and Permissions
- **Dommer (Judge)**: Can claim cases, move cases, close cases
- **Administrator**: Can set up categories, assign judges, view statistics
- **Klient (Client)**: Regular users who can open tickets
- **Specified roles**: Additional roles that can be pinged when tickets are created

### Case Management System
- No limit on the number of tickets/cases
- Each case gets a unique case number automatically
- Cases can have different statuses: Åpen (Open), Under behandling (In Progress), Lukket (Closed), Anket (Appealed)
- Case archiving system:
  - When a case is closed, all messages are compiled into an HTML document
  - The document is posted in a dedicated "arkiv" category
  - The archive includes searchable text specifics for easy reference
- Ticket channel naming format: serverDisplayName-SakId (where SakId is an incrementing integer)
- Channel names can be edited, but the system identifies tickets by channel ID, not channel name

### Judge Quarters System
- Each judge has their own "quarters" (category)
- When a judge claims a case, it moves to their quarters
- Judges can send cases to other categories if needed

### Notification System
- Scheduled DM notifications for hearings and other events
- Automatic notifications when case status changes
- Notifications when new evidence is submitted
- Direct DM system for judges to contact participants

### Evidence Management
- Evidence can be added to cases with descriptions and links
- Evidence can be retrieved by case ID without scrolling through chat
- Evidence is included in case exports and archives

### Complete Command List

#### Setup Commands
- [x] `/oppsett` - Initial setup for the bot in a server
- [x] `/sett-dommer <bruker> <kategori-navn>` - Sets up a judge's quarters with the specified category name
- [x] `/fjern-dommer <bruker>` - Removes a judge's quarters

#### Ticket Management
- [x] `/ticket <category> <title> <description> <button-emoji> <button-text> <role>` - Creates a ticket button in the channel it was typed in, it will then open new tickets in the <category>
- [x] `/lukk-sak` - Closes the current ticket and archives it
- [x] `/arkiver-sak` - Archives the current ticket without closing it
- [x] `/avslutt-sak <grunnlag>` - Closes the case with specified reason, notifies the opener via DM, exports to HTML, uploads to audit log, then closes the ticket (only if all steps succeeded)

#### Judge Commands
- [x] `/ta-sak` - Claims the current case and moves it to the judge's quarters
- [x] `/send-sak <kategori>` - Sends the current case to a different category. Make sure to add the role to the ticket when moving it.
- [x] `/legg-til-notat <tekst>` - Adds a note to the case file
- [x] `/vis-saker <bruker>` - Shows all cases assigned to the judge
- [x] `/vis-åpne-saker` - Shows all open cases in the system
- [x] `/send-dm <bruker> <tekst>` - Allows judges to send DMs to people through the bot

## Features
- send-sak will only send a sak to a registered category, meaning it will not send the sak to a category that is not registered
- The registered categories

#### Notification Commands
- [x] `/varsle-klient <bruker> <dato> <tid> <melding>` - Schedules a DM to be sent to a user
- [x] `/avbryt-varsel <varsel-id>` - Cancels a scheduled notification
- [x] `/vis-varsler` - Shows all scheduled notifications

#### Evidence and Documentation
- [x] `/legg-til-bevis <kort beskrivelse eller navn> <dokument-link>` - Adds evidence to the case with description and link, and adds a sub-id to the evidence, meaning a sak-id plus a sub-id so sak 1 can have evidence 1.1, 1.2, and 1.3. That way it's easier to reference specific evidence for other cases.
- [x] `/fjern-bevis <bevis-id>` - Removes evidence from the case
- [x] `/vis-bevis` - Shows all evidence in the current case
- [x] `/hent-bevis <sak-id>` - Retrieves a list of evidence for the specified case ID
- [x] `/eksporter-sak` - Exports the current case as an HTML document in the ticket

#### Case Information
- [x] `/sak-info <sak-id>` - Shows detailed case information including evidence, reason opened, reason closed, date and other metadata
- [x] `/søk-arkiv <søkeord>` - Searches the archive for specific terms, displays top 10 most recent results in a paginator with case name and ID

#### Administrative Commands
- [x] `/statistikk` - Shows statistics about cases and judges
- [x] `/hjelp` - Shows help information about all commands
- [x] `/registrer-kategori <navn> <rolle>` - Registers a new category seperate from judge quarter categories, where a role instead of a judge has the ability to view added tickets. 
- [x] `/sett-rolle <rolle-funksjon> <rolle>` - Sets permissions for different bot functions to specific roles
- [x] `/vis-roller` - Shows all role permissions for bot functions

### Implementation Details
- All data will be stored in an SQL database (.db file)
- Case archiving will generate HTML documents for easy viewing
- The bot will handle scheduled notifications even if restarted
- Permissions will be strictly enforced based on user roles
- All user-facing text will be in Norwegian
- When closing a case, the system will:
  1. Export to HTML
  2. Save and upload to audit log
  3. Double check export success
  4. Close ticket or throw error if any step fails

### Additional Information From Previous Chats

So I believe that we should have case management system.
Also there should be no limit on amount of tickets.
Case archiving should be a text channel in a another category named "arkiv" with archived cases where the bot takes all the messages in a ticket and makes it into an html downloadable document and posts it to the log with text specifics so you can search through.
I also like the notificaiton system, let's add a command to /varsle klient and pick a date and time to send a DM, basically a scheduled DM.
I want it all to be sql .db.

When setting up the quarters for a judge you just type /sett-dommer <bruker> <kategori-navn> and it auto sets it all up. That means when a new ticket is opened in said category and a judge types /ta-sak it will be sent to their category automatically. But if they type /send-sak <category> they can choose from all categories in the server.

You got any other suggestions? Could you also perhaps add to the plan.md on all commands we need, like ALL?

How about also adding /avslutt sak <grunnlag>, which will notify in DMs to the user that opened the case it has been closed and archived. When it is avslutted it will be exported as an html first, then saved and uploaded in the audit log Then if no errors and double check it was exported and saved then it will close the ticket or throw an error.

Also for /legg-til-bevis <kort beskrivelse eller navn> <dokument-link>, where in a ticket channel if someone ever needs the evidence without scrolling through the whole chat. They can type /hent-bevis <sak-id> and get a list of documents
/sak info <sak-id> which will give them a list of evidence, reason it was opened, reason it was closed as well as well as date.
We can also use the /søk-arkiv <søkeord> command where it will search all the sak info stuff and check for those, it will then give a result with top 10 results in a paginator with the most recent first. It will then have the name of the case and id only, that way they can use sak info to get more in-depth info


Make sure that the ticket channel names are in this format: serverDisplayName-SakId
Where the SakId is just an integer which keeps rising with all cases registered.

But the ticket channel names should be able to be edited in case a judge needs that for context, so the sak-id on a ticket channel has to be connected with the channel id never the name.

Also add a /send-dm <bruker> <tekst> kommand, that allows judges to send DMs to people. Make sure the bot checks if it

I didn't like any of your suggestions so far, add what I said.