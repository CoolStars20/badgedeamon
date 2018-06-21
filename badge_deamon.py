import sys
import os
import smtplib
import subprocess
import shutil
from warnings import warn
from tempfile import TemporaryDirectory
from email.message import EmailMessage
import re
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from astropy.table import Table
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sqlite3
import imaplib

reg_subject = re.compile('\[#(?P<id>[0-9]+)\]')
reg_newname = re.compile('REPLACE NAME: (?!Mr. E. Xample)(?P<name>[\w\s]+)')
reg_newaffiliation = re.compile('REPLACE AFFILIATION: (?!Institute of Example)(?P<affil>[\w\s]+)')
badge_images = '/melkor/d1/guenther/projects/cs20/badgeimages'
ready_badges = '/melkor/d1/guenther/projects/cs20/badges/'
default_image = '/melkor/d1/guenther/projects/cs20/badgedeamon/Cs20logoround.png'
default_image = '/melkor/d1/guenther/projects/cs20/badgedeamon/kitty.jpeg'
textemplate = 'badge_template.tex'

with open('../../gmail.txt') as f:
    password = f.read()
password = password[:-1]

conn = sqlite3.connect('badges.db')
c = conn.cursor()


def send_email(msg):
    with smtplib.SMTP('smtp.gmail.com', 587) as s:
        s.ehlo()
        s.starttls()
        s.login(msg['From'], password)
    s.send_message(msg)


def test_regid_known(regid):
    c.execute('SELECT COUNT(*) FROM badges WHERE regid = ?', regid)
    return c.fetchone()[0] == 1


def find_save_name_inst(regid, mail):
    textplain = None
    texthtml = None
    name = None
    affile = None
    for part in mail.walk():
        if part.get_content_maintype() == 'text':
            if part.get_content_subtype() == 'plain':
                textplain = part.get_payload().splitlines()
            if part.get_content_subtype() == 'html':
                texthtml = part.get_payload()
                # Remove obvious html tags. This method can be fooled and html
                # tags and remain, but that's not a security risk for
                # this application
                re.sub('<[^<]+?>', '', texthtml)
                texthtml = texthtml.splitlines()
    if (textplain is None) and (texthtml is None):
        return None, None
    else:
        text = texthtml if (textplain is None) else textplain
        for l in text:
            m = reg_newname.match(l)
            a = reg_newaffiliation.match(l)
            if m is not None:
                name = m['Name']
            if a is not None:
                affil = a['affil']
        return name, affil


def find_first_suitable_image(regid, mail):
    image = None
    warntext = ''
    for part in mail.walk():
        if part.get_content_maintype() == 'multipart':
            # print part.as_string()
            continue
        if part.get('Content-Disposition') is None:
            # print part.as_string()
            continue
        fileName = part.get_filename()
        if bool(fileName):
            extension = fileName.split('.')[-1]
            if extension.lower() not in ['jpg', 'jpeg', 'png']:
                continue
            else:
                filePath = os.path.join(badge_images, reg_id + '_' + fileName)
                if image is None:
                    with open(filePath, 'wb') as fp:
                        fp.write(part.get_payload(decode=True))
                    image = filePath
                else:
                    warntext = "More than one image file was attached to your message. I'm using the first one of those for your badge.\n"
    if image is None:
        warntext = "No file ending on 'jpg', 'jpeg' or 'png' was attached to your email. I'm using whatever file you previously submitted or (if you did not submit a file with a previous email) a default image.\n"
    return image, warntext


def compile_pdf(regid, dat):
    template = env.get_template('badge.tex')
    with TemporaryDirectory() as tempdir:
        with open(os.path.join(tempdir, 'badge_{}.tex'.format(regid)), "w") as tex_out:
            tex_out.write(template.render(dat=dat))

        out = 'Rerun'
        while 'Rerun' in str(out):
            latex = subprocess.Popen(['xelatex', '-interaction=nonstopmode',
                                      os.path.join(tempdir, 'abstract')],
                                     cwd=tempdir,
                                     stdout=subprocess.PIPE)
            out, err = latex.communicate()
        shutil.copy(os.path.join(tempdir, 'badge_{}.pdf'.format(regid)),
                    ready_badges)


def compose_email(email, regid, warntext=''):


imapSession = imaplib.IMAP4_SSL('imap.gmail.com')
typ, accountDetails = imapSession.login('coolstarsbot@gmail.com', password)
    if typ != 'OK':
        raise Exception('Not able to sign in!')

    imapSession.select('Inbox')
    typ, data = imapSession.search(None, 'unseen')
    if typ != 'OK':
        raise Exception('Error searching Inbox.')

    for msgId in data[0].split():

        attachment_found = []
        typ, messageParts = imapSession.fetch(msgId, '(RFC822)')
        if typ != 'OK':
            raise Exception('Error fetching mail.')

        emailBody = messageParts[0][1]
        mail = email.message_from_bytes(emailBody)
        match = reg_subject.search(mail['SUBJECT'])
        if match is None:
            # Header does not have message ID in it -> forward to Moritz
            mail.replace_header('From', 'coolstarsbot@gmail.com')
            mail.replace_header('To', 'hgunther@mit.edu')
            send_email(mail)
        else:
            regid = match['id']
            if not test_regid_known(regid):
                mail.replace_header('From', 'coolstarsbot@gmail.com')
                mail.replace_header('To', 'hgunther@mit.edu')
                send_email(mail)
            else:
                image, warntext = find_save_first_suitable_image(regid, mail)
                name, inst = find_name_inst(regid, mail)
                if image is not None:
                    c.execute('UPDATE badges SET image=? WHERE regid=?', (image, regid))
                if name is not None:
                    c.execute('UPDATE badges SET name=? WHERE regid=?', (name, regid))
                if inst is not None:
                    c.execute('UPDATE badges SET affil=? WHERE regid=?', (inst, regid))

                c.execute('SELECT * FROM badges WHERE regid=?', regid)
                regid, name, affil, image, email = c.fetchone()
                if image == 'default':
                    image = default_image
                compile_pdf(regid, {'image': image, 'name': name, 'inst': inst})
