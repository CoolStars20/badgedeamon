import sqlite3
import numpy as np
from astropy.table import Table

tab = Table.read('../data/reglist3.csv')

conn = sqlite3.connect('badges.db')
c = conn.cursor()
# Create table
c.execute('''CREATE TABLE badges
             (regid text, pronoun text, name text, affil text, image1 text, image2 text, email text, role text)''')

for row in tab:
    text = ''
    if row['days']:
        text = row['days']
    if row['group']:
        text = row['group']
    c.execute("INSERT INTO badges VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (
                  int(row['Tran#']),
                  '',  # Default is no pronoun
                  row['First Name'] + ' ' + row['Last Name'],
                  row['Institution'],
                  "default1.png",
                  "default2.jpeg",
                  row['Email Address'],
                  text))  # LOC, SOC, Mon/Tue, ...

conn.commit()
conn.close()
