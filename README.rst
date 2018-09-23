============
Badge-deamon
============

#### What is this?

These instructions are so detailed that a casual Python user can hopefully follow them, but if the terms "cron job", "Python code" or "SQLite" mean nothing to you, I recommend to find another LOC member to take on this task.

What do I need?
===============

- Python 3 and jinja2
- the file badge_deamon.py
- templates for emails and badges
- an email account
- some disk space
- pdflatex or similar (e.g. LuaTex, XeTeX)

Python 3
--------
The code is written in Python 3. It uses mostly modules from the standard library. The only other package we use is `jinja2 <http://jinja.pocoo.org/>`_ . Personally, I like to install my Python packages from the `Anaconda distribution <https://www.anaconda.com/download/>`_, but really any Python installation will do; if jinja2 is not included, just try ``pip install jinja2``.

Files
-----
Copy the file ``badge_deamon.py`` from this repository to a directory on your disk. Edit that file with your path, your email address, etc. The file is extensively commented. It's the only file you really need from this repository; everything else are documentation files (like this file), examples for tex templates, or examples in python to setup the database.

An email account
----------------
Users interact with the bot by sending emails to an email address and the bot will reply with a rendered badge by email again. For a conference with 500 attendees we send and received about 1500 emails each (most people only write once, but some play around and submit try out differenct variants of spelling etc. to make it fit). That's far more email than you want in your personal account. So, make a dedicated email account for this. We used a free gmail account. Two things to keep in mind: First, gmail imposes `a limit of 500 emails in 24 h <https://support.google.com/mail/answer/22839?hl=en>`_ to prevent people from sending spam (this is common, e.g. my university email address has a similar limit) and second, the current version of the code just saves the password in plan text in a file; thus if you use gmail you have to `allow less secure apps <https://support.google.com/accounts/answer/6010255?hl=en>`_. That's obviously not good practice; using an API key or other safeer machanism would be better. I welcome your pull requests to improve the code!

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

To do that, you can work directly with `SQLite on the command line <http://www.sqlitetutorial.net/sqlite-import-csv/>`_, use any other scipt that might be handy, or write code in Python. As an example, this repository contains a file ``create_badge_table.csv`` that shows how to read a csv file and write a ``badges.db`` file.  Our admin gave us a Microsoft Excel file with the registration information, so we exported it as csv and worked from there).

Start cron job
--------------
Next, start a program that runs the badge deamon every few minutes. You could of course just run it manually once a day, but it's much better to run it every few minutes so that people get a new badge fast and can iterate if it still does not look right.

I set up a cronjob on my linux machine to run every 2 minutes. ``crontab -e`` opens an editor where I add the following line to my crontab::

   */2 * * * * /nfs/melkor/d1/guenther/soft/anaconda/envs/py3/bin/python /melkor/d1/guenther/projects/cs20/badgedeamon/badge_deamon.py

The first part `*/2 * * * *` runs this command every two minutes for every hour, every day, every months, and every year. Note that I call Python with the full path to make sure I run Python 3 in the right environment (and not my system Python which is still Python 2). Depending on how your Python was installed, your path will be different.

If you ever need to pause and not run your script for a while, just run `crontab -e` again and add a `#` as first character of the line with comments it out.
   
Test
----
Test. Test, and test again. Email to your email address to modify your own badge, add random pictures, use obscure LaTeX commands and see what happens. I guarantee that there will be typos in the path name or the password for your eamil account is not set correctly or there is some problem with your LaTeX template. The way the script is currently written, it does not preserve and show you the log, so it's a little hard ot find out what went wrong. (I appreciate your help to improve this.) So, I suggest to fill in your LaTeX template manually, run it with `pdflatex` and check that is works. You can also fire up an interactive Python session,  and then use and test the individual functions, e.g. try to connect to your email server and download any unread messages with::

  >>> import badge_deamon
  >>> out = bade_deamon.retrieve_new_messages()

and debug any problems.
You don't have to send new emails every time. The code downloads any unread messages in your email account. If you use e.g. Gmail, you can watch your inbox in the webbrowser and mark a message as "unread" again so that the program downloads it again for your next test.

Once everything works, invite your LOC to test it out and once that all works, proceed to the next step.

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

Replace your default images. The database only stores the name of the image file, for example "default_front.png". When you send out the initial emails, "default_front.png" may have been an imge of a cute kitty with a watermark saying "sample image" (that is the default that we provide in this repository) to encourage everyone to send in their own image. However, it would be unprofessional to print that on the real badges. So, just replace the file "default_front.png" with a new image for people who did not submit anything, for example your conference logo, and save it with the same filename. Run pdflatex again for every badge::

  >>> import badge_deamon
  >>> import sqlite3
  >>> conn = sqlite3.connect('badges.db')
  >>> c = conn.cursor()
  >>> badge_deamon.prepare_badge_pdf(c, [i for i in range(123)])

Print one badge again to test that the paper size is correct (look for "scale to printible area" or similar settings in the pdf reader if it does not fit), then print them all!

People may continue to send you emails until the conference starts. So, we changed the text of our email template, adding *Unfortunately, we printed the badges already. You can continue to update your name and images, if you print out the badge yourself and bring it with you to the registtration desk*. Then, we activated the cron job again. About a dozen people printed their own badges and we used their printouts at the registration.


What problems will happen?
==========================


Support, feedback, improvements
===============================

If something fails and you can't figure out why on your own and you can `open an issue <>`_, shoot me an email (hgunther@mit.edu).

I welcome any feedback and your ideas for improvement; I know that there are few things that could be done better but I don't know how to solve that or did not yet have the time to do so. The best way to help me is to open a pull request to the badgedeamon github repository at https://github.com/CoolStars20/badgedeamon .
