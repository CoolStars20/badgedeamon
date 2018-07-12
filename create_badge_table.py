import sqlite3
import numpy as np

conn = sqlite3.connect('example.db')

c = conn.cursor()
# Create table
c.execute('''CREATE TABLE badges
             (regid integer, pronoun text, name text, affil text, image1 text, image2 text, email text, title text)''')
# Split by both ; and , to make short enough
tab3['affil'] = ['' if r is np.ma.masked else r.split(';')[0].split(',')[0].strip() for r in tab3['Affiliations']]

# got tab3 from match_reglists script
for row in tab3:
    c.execute("INSERT INTO badges VALUES (?, ?, ?, ?, ?)",
              (
                  row['Tran#'],
                  '',  # Default is no pronoun
                  row['First author'] if not row['First author'] is np.ma.masked else ' '.join((row['First Name'], row['Last Name'])),
                  row['affil'],
                  "default",
                  "default"
                  row['Email Address'],
                  ''))  # LOC, SOC, Mon/Tue, ...

tab3['First author', 'First Name', 'Last Name', 'Tran#', 'affil', 'Email Address']


conn.commit()
conn.close()
