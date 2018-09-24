============
Badge-deamon
============

Badge-deamon is a way to customize conference badges for every conference attendee with pictures that the attendees submit by eamil.
Each attendee gets an email message from the bot script, and by replying to this email message, they can change the information shown on the badge or add custom images to their badge. These images can show for example a plot from their talk, the logo of their new project, or any visualization related to their field of study. These images are meant as conversation starters at receptions, breaks, or other social events.

At the same time, we found it useful to allow conference attendees to customize their name (some people use their middle names, others don't, or some have special characters in their name that our registration system did not handle correctly), their affiliation (e.g. for a recent affiliation change or to shorten long names for readability), and their preferred pronoun (e.g. for people who do not identify as either male or female).

This repository holds a Python script `badge-deamon.py` which will download new emails, parse those emails to find the changes requested, update the participant database, make a new pdf for the conference badge with those updates and send it back by email so that the conference participant can check that everything looks good after the change.

Our layout is for a 6" * 4" (about 15 cm * 10 cm) badge with a conference logo at the top, then participant pronoun, name, and affiliation, and space for an image below. At the very bottom, the script can include a color bar with a label (e.g. green for "LOC" members, orange for "panel speaker" etc.); those badges have a little less space for the image. We allow two different images (one for the front and one for the back) and we printed front and back next to each other on the a standard laser printer. Using a large paper cutter we cut about 20 sheets and once and at the registration we folded the paper and inserted into a badge holder. There are probably many companies that offer large badge holders; we used a badge holder from marcopromos <https://www.marcopromos.com/Product/Top-Loading-All-Purpose-Vinyl-Badge-Holders---6-x-4---No-Attachment-HSE-8-NA-96108.htm>`_.

We used this method for the `20th Cambridge workshop of Cool Stars, Stellar Systems and the Sun <https://coolstars20.github.io/>`_. About 90% of the attendees customized their badge, and many people told us they loved this feature. Cool Stars had over 500 attendees - far to many to do this without an automated program. So, after the conference, I edited our script to make it more general and I wrote these instructions so that you can use my script for your own conference, too.

These instructions are so detailed that a casual Python user can hopefully follow them, but if the terms "cron job", "Python code" or "SQLite" mean nothing to you, I recommend to find another member of your organizing comitee to take on this task.

What do I need?
===============

- Python 3 and jinja2
- the file `badge_deamon.py` from this repository
- templates for emails and badges
- an email account
- some disk space
- pdflatex or similar (e.g. LuaTex, XeTeX)

Python 3
--------
The code is written in Python 3. It uses mostly modules from the standard library. The only other package we use is `jinja2 <http://jinja.pocoo.org/>`_ . Personally, I like to install my Python packages from the `Anaconda distribution <https://www.anaconda.com/download/>`_, but really any Python installation will do; if jinja2 is not included, just try ``pip install jinja2``.

Files
-----
Copy the file ``badge_deamon.py`` from this repository to a directory on your disk. Edit that file with your path, your email address, etc. The file is extensively commented. It's the only piece of Python code you really need from this repository; everything else are documentation files (like this file), examples for tex templates, or examples in python to setup the database.

An email account
----------------
Users interact with the bot by sending emails to an email address and the bot will reply with a rendered badge by email again. For a conference with 500 attendees we send and received about 1500 emails each (most people only write once, but some play around and try out several different figures). That's far more email than you want in your personal account. So, make a dedicated email account for this. We used a free gmail account, coolstarsbot@gamil.com. Two things to keep in mind: First, Gmail (and most other providers) impose `a limit of 500 emails in 24 h <https://support.google.com/mail/answer/22839?hl=en>`_ to prevent people from sending spam and second, the current version of this code just saves the email password in plain text in a file; thus if you use gmail you have to `allow less secure apps <https://support.google.com/accounts/answer/6010255?hl=en>`_. That's obviously not good practice; using an API key or other safer machanism would be better. I welcome your pull requests to improve the code!

Some disk space
---------------
Not much, but the current version of the code does not limit file sizes, so make sure your computer does not go down if 500 people send you 20 MB big images each. In principle, an attacker could try to bring down your system by attaching GB sized images, but in practice your email provider will probabably not accept email over 20 MB or so anyway, so you are safe.

LaTeX
-----
The current version of the code runs *pdflatex*. It might be useful to change that to a more modern tex engine like LuaTeX or XeLaTeX with better unicode support, but pdflatex worked for us. It's easy to change in the Python file.

How do I set it up?
===================

Prepare files and directories
-----------------------------
Make a new empty directory on your disk. In this directory, copy ``badge_deamon.py`` from this repository. Some more files that could live in that directory are:

- the templates for the email text that you want ot send out,
- the tex template to make the badge (examples for those are in this repository),
- the sqlite database ``badges.db``, and
- a few images like the default images or logos that are part of your tex templates.

I recommend two more empty directories: One directory to store the uploaded pictures and one to store the finished badges. 

Set up ``badge_deamon.py``
--------------------------
Edit ``badge_deamon.py`` to set the right file names and paths to everything (detailed instructions are in that file).

Initialize sqlite database ``badges.db``
----------------------------------------
All information for the badges is stored in an `sqlite database <https://sqlite.org>`_. SQLite itself and Python routines to work with SQLite databases are part of the standard Python distribution, so you don't have to install anything special. SQLite databases are stored in a single, normal file on your disk and are perfect for small projects like this one. The Python code stores all information like name, registration number, affiliation, images submitted etc. in an SQLite database. Thus, before you can start, you need to set up the SQLite database and fill it with (at a minimum) registration numbers and email addresses, plus some defaults for the other fields in the database. 

To do that, you can work directly with `SQLite on the command line <http://www.sqlitetutorial.net/sqlite-import-csv/>`_, use any other scipt that might be handy, or write code in Python. As an example, this repository contains a file ``create_badge_table.csv`` that shows how to read a csv file and write a ``badges.db`` file.  Our admin gave us a Microsoft Excel file with the registration information, so we exported it as csv and worked from there.

Start cron job
--------------
Next, start a program that runs the badge deamon every few minutes. You could of course just run it manually once a day, but it's much better to run it every few minutes so that people get a new badge fast and can iterate if it still does not look right.

I set up a cronjob on my linux machine to run every 2 minutes. ``crontab -e`` opens an editor where I add the following line to my crontab::

   */2 * * * * /nfs/melkor/d1/guenther/soft/anaconda/envs/py3/bin/python /melkor/d1/guenther/projects/cs20/badgedeamon/badge_deamon.py

The first part `*/2 * * * *` runs this command every two minutes for every hour, every day, every months, and every year. Note that I call Python with the full path to make sure I run Python 3 in the right environment (and not my system Python which is still Python 2). Depending on how your Python was installed, your path will be different. Then, I give the full absolute path to the badge deamon script.

If you ever need to pause and not run your script for a while, just run `crontab -e` again and add a `#` as first character of the line to comment it out.
   
Test
----
Test. Test, and test again. Send an email to your email address to modify your own badge, add random pictures, use obscure LaTeX commands and see what happens. I guarantee that there will be typos in the path name or the password for your eamil account is not set correctly or there is some problem with your LaTeX template. The way the script is currently written, it does not preserve and show you the log, so it's a little hard ot find out what went wrong. (I appreciate your help to improve this.) So, I suggest to fill in your LaTeX template manually, run it with `pdflatex` and check that it works. You can also fire up an interactive Python session,  and then use and test the individual functions, e.g. try to connect to your email server and download any unread messages with::

  >>> import badge_deamon
  >>> out = badge_deamon.retrieve_new_messages()

and debug any problems.
You don't have to send new emails every time. The code downloads any unread messages in your email account. If you use e.g. Gmail, you can watch your inbox in the webbrowser and mark a message as "unread" again so that the program downloads it again for your next test.

Once everything works, invite your organizing comitee to test it out and once that all works, proceed to the next step.

Print one of your badges and make sure it fits your badge holders, so you can adjust the LaTeX template if it's too big or too small.
  
Send out initial emails
-----------------------
Send emails to your conference attendees with a draft badge so that they can look at it, and reply to that email to update name, affiliation or pictures. In the following example, the registration numbers are 0 to 122::

  >>> import badge_deamon
  >>> import sqlite3
  >>> conn = sqlite3.connect('badges.db')
  >>> c = conn.cursor()
  >>> badge_deamon.email_for_regids(c, [i for i in range(123)])
  >>> conn.commit()
  >>> conn.close()

If you have a big conference, do not email everybody at once. We used a GMail account with a limit of 500 email in 24 h, so we emailed about 150 people on Friday evening. About a thrid of all people replied the same evening, so our bot send them a new badge (some of them emailed several times), but we stayed comfortabley below the limit of 500. So, we emailed the next 250 people 24 h later on Saturday evening and the remaining 100 people on Sunday evening. That way, we never reached the 500 emails per day limit.


Sit back, relax and back-up
---------------------------
Log into your email account and check a few incoming and outgoing emails to make sure everything works. If you see emails in the "inbox", but nothing in the "send" folder, your script does not work. Don't panic. Find out what is wrong and fix it. If some emails were not processed, just mark them as "unread" again and a few minutes later when your script rund again, it will download them again and try again.

Also, on your local disk, you should see images appear in the image directory and badges in the badge output directory.

It's a good idea to back up the directory with the images and `badges.pdb`, just in case. If you keep all emails in your inbox, you could always mark them all as "unread" and process everything again if the files on your computer are lost, bit it's better to be safe then sorry.


Print final badges
------------------
Print our badges a few days before the conference. Stop the cron job because it's confusing to have new images appear while you try to clean everything up.

Replace your default images. The database only stores the name of the image file, for example "default_front.png". When you send out the initial emails, "default_front.png" may have been an imge of a cute kitty with a watermark saying "sample image" (that is the default that we provide in this repository) to encourage everyone to send in their own image. However, it would be unprofessional to print that on the real badges. So, just replace the file "default_front.png" with your conference logo for people who did not submit anything, and save it with the same filename. Run pdflatex again for every badge::

  >>> import badge_deamon
  >>> import sqlite3
  >>> conn = sqlite3.connect('badges.db')
  >>> c = conn.cursor()
  >>> badge_deamon.prepare_badge_pdf(c, [i for i in range(123)])

Print one badge again to test that the paper size is correct (look for "scale to printible area" or similar settings in the pdf reader if it does not fit), then print them all! If the paper size is a little to bog or small, scale it a little in the printer dialog or adjust the LaTeX template and run the code above again to re-generate the pdfs.

People may continue to send you emails until the conference starts. So, we changed the text of our email template, adding *Unfortunately, we printed the badges already. You can continue to update your name and images but you need to print out the badge yourself and bring it with you to the registtration desk*. Then, we activated the cron job again. About a dozen people printed their own badges and we used their printouts at the registration.

A note about paper: We just printed on standard laser printer paper with front and back page next to each other, cut it out, and folded the paper. That way each badge can (i) still be read if it flips around and (ii) has two layers of paper. If you want to print front and back, you need to adjust our LaTeX template and also use a thicker cardstock paper. You can also get perforadted paper in the right size, e.g. `this <https://www.marcopromos.com/Product/Premium-Blank-Laser-Insert-Stock---6-x-4---White---Pack-of-500-A-8LI-P-WE-153477.htm>`_.


Other changes to the database
=============================
If you need to do things to the SQLite database (e.g. add new registrations, add a new column), don't forget::

  >>> conn.commit()
  >>> conn.close()

If you don't type that, your commits won't be saved. 
  
Also, stop the cron job. I chose a real database for this job (and not e.g. just a csv table) because it's possible to access the same database form different processes at the same time. However, you can read from the database easily, but if you do a change, it's lokced to other processes, until you do `conn.commit()`. If `badge_bot.py` processes a new email and trys to update the database and the database does not become unlocked within a few seconds, it will silently fail, so, unless oyu type really fast, better pause the cron job while you do complex changes to your database by hand.

Check out the `Python documentation for SQLite <https://docs.python.org/3/library/sqlite3.html>`_ and the `SQLite documentation <https://sqlite.org/lang.html>`_ for help how to add columns, add more rows, etc.

Possible problems and security
==============================
This script has a number of issues that an attacker could use to disturb your operation. For Cool Stars none of the following attacks happened and most people who want to attend your conference will probably play nice. In the end, this is not a crucial application. If it fails, you cna still print badges with a standard image for everyone. However, I want to list a few problems that I am aware of here so you cna look out for it - I also appreciate pull requests to improve the code:

- Name changes: People could change their name to anything, not just from "Hans Guenther" to "Hans M. Guenther", but also to "Kim Smith". We did not allow transfer of a registration to somebody else, so I looked at the initial names in the database and the final names afte all changes that took me about 5 min for 500 people.
- Offensive content: We looked at every badge as we printed it and cut the paper (about 1 hour to flip though a pdf with 500 draft badges). If we had seen any image that violated our Code of Conduct, we would have replaced it with a blank badge but that did not come up.
- Attendees who don't care: We had about a dozen (2% of all attendees) badges that where obviously wrong or unreadable (e.g. affiliation so long that it runs off the page or attendee name="New Name here: New name here"). Either those people did not bother to check that their badge come out right or they missed our email in thier spam filter or because they were on vacation or something. We fixed those by hand before we printed the badges (as I said in the last point, we flipped through a large pdf with all badges before we printed it).
- email spam: The script processes and answers every email. If an attendee has a script that ansers back, you can fire back and forth and quickly reach the 500 email per day limit. Fortunately, automatic "vacation reply" email typically don't do that.
- Changes for wrong attendee. The `badge_deamon` looks in the subject line for the registration number. Nothing stops an attacker from putting the wrong number in there to change the badge of someone else. If you think that might happen, don't use consequtive registration ids, but make them long and random strings.
- LaTeX vulnerabilities: The bades are processed with LaTeX. People can send arbitrary LaTeX code and that is not safe, see https://0day.work/hacking-with-latex/ . Since we want to allow attendees to send LaTeX for any character they might have in their name or affiliation, I don't know a way around that. However, I believe that restricting the length of the string for name and affiliation should block this attack.


Support, feedback, improvements
===============================

If something fails and you can't figure out why on your own and you can `open an issue <https://github.com/CoolStars20/badgedeamon/issues/new>`_ or shoot me an email (hgunther@mit.edu).

I welcome any feedback and your ideas for improvement; I know that there are few things that could be done better but I don't know how to solve that or did not yet have the time to do so. The best way to help me is to open a pull request to the badgedeamon github repository at https://github.com/CoolStars20/badgedeamon .

Acknowledgements
================
The idea to customize images for conference badges is not mine. I saw that in a Harvard-Heidelberg Workshop organized by Alyssa Goodman, who in turn borrowed that idea from Felice Frankel. Felice has used it for a number of conferences since 2001.

Note that we are not affiliated in any way with any of the sellers of badge holders etc. linkes above. Do your own research. I just want to give an example how these things might look.