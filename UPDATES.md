# Updates

This doc includes updates toward the app UI.

1. Color coded function buttons
 - Let the user choose a color for each function button generated from the config file.
 - Inside the config editor screen, for each row, create a drop-down for the color selection.
 - place the drop-down between the string input widget and remove button

2. Chevrons for RX/TX
- draw chevrons `>>` (TX) and `<<` (RX) inside the datastream log to indicate TX and RX streams
- make the chevrons toggle-able and depending on toggle write it to the log file same as timestamps

3. Labels for TCP/IP device connections
- Add an Input widget below the TCP Port widget in the TCP/IP device connection tab
- Let the user input a label for the device and display the label in the workspace tab for that device
- also save the label to the favorites

4. Command History List
- Display a List widget showing the user's command history
- Put the config file drop down and function buttons window in a tabbed content window
- Display the command history list as a tab

```python

# Tabbed Content, Label: Functions
yield Select([], id="command-config-select", prompt="Select command config", allow_blank=True)
yield VerticalScroll(id="command-buttons-scroll")

# New Content in 2nd Tab, Label: History
# yield VerticalScroll(id="command-history-scroll") ??
yield List([], id="command-history-list", classes="command-history-list")

```