importlib.reload(badge_deamon)

sendnow = tab['send'].mask
sendnow[220:] = False
numberlist = list(tab['Tran#'][sendnow])
badge_deamon.email_for_regids(c, numberlist)
conn.commit()
tab['send'][sendnow] = True
tab['First Name',
 'Last Name',
 'Institution',
 'Tran#',
 'Email Address',
 'days',
 'group',
 'sen'].write('tab.csv', format='ascii.csv')
