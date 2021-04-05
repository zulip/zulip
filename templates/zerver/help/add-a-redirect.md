# Add a redirect from an old URL to a new URL

{!admin-only.md!}

In order to add a redirect from a certain web page URL that has been updated to another, 
Use the dictionary item created in `zerver/views/documentation.py` named with a function `help_center_redirects` .It contains and returns the dictionary of matching old URLs as key values and the new URLs as their respective pair values. You cannot have duplicate OLD URL values. Edit the `redirects_table` dictionary in the `key : value` pair format as stated above for any changes made.