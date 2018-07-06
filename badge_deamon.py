import os
import smtplib
import subprocess
import shutil
from tempfile import TemporaryDirectory
from email.message import EmailMessage
import re
from jinja2 import Environment, FileSystemLoader
import sqlite3
import imaplib
import email

reg_subject = re.compile('\[#(?P<id>[0-9]+)\]')
reg_newname = re.compile('REPLACE NAME:(?!Mr. E. Xample)(?P<name>[\S\s]+)', re.IGNORECASE)
reg_newaffiliation = re.compile('REPLACE AFFILIATION:(?!Institute of Example)(?P<affil>[\S\s]+)', re.IGNORECASE)
badge_images = '/melkor/d1/guenther/projects/cs20/badgeimages'
ready_badges = '/melkor/d1/guenther/projects/cs20/badges/'
default_image = '/melkor/d1/guenther/projects/cs20/badgedeamon/Cs20logoround.png'
default_image = '/melkor/d1/guenther/projects/cs20/badgedeamon/kitty.jpeg'
textemplate = 'badge_template.tex'
selfpath = os.path.dirname(__file__)

# Load password
with open(os.path.join(selfpath, '..', 'gmail.txt')) as f:
    password = f.read()
password = password[:-1]

# set up jinja
env = Environment(loader=FileSystemLoader([selfpath]))


def send_emails(msg):
    with smtplib.SMTP('smtp.gmail.com', 587) as s:
        s.ehlo()
        s.starttls()
        s.login(msg[0]['From'], password)
        for m in msg:
            s.send_message(m)


def test_regid_known(c, regid):
    c.execute('SELECT COUNT(*) FROM badges WHERE regid = ?', [str(regid)])
    return c.fetchone()[0] == 1


def find_name_inst(regid, mail):
    textplain = None
    texthtml = None
    name = None
    affil = None
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
                name = m['name']
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
            if extension.lower() not in ['jpg', 'jpeg', 'png', 'pdf']:
                continue
            else:
                filePath = os.path.join(badge_images, regid + '_' + fileName)
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
    template = env.get_template('badge_template.tex')
    with TemporaryDirectory() as tempdir:
        with open(os.path.join(tempdir, 'badge_{}.tex'.format(regid)), "w") as tex_out:
            tex_out.write(template.render(dat=dat))
        shutil.copy(os.path.join(selfpath, 'csheader.jpg'), tempdir)
        latex = subprocess.Popen(['pdflatex', '-interaction=nonstopmode',
                                  'badge_{}.tex'.format(regid)],
                                 cwd=tempdir,
                                 stdout=subprocess.PIPE)
        out, err = latex.communicate()
        shutil.copy(os.path.join(tempdir, 'badge_{}.pdf'.format(regid)),
                    ready_badges)


def compose_email(emailaddr, regid, name, warntext=''):
    template = env.get_template('email_template.txt')
    # Create the container email message.
    msg = EmailMessage()
    msg['From'] = 'coolstarsbot@gmail.com'
    msg['To'] = emailaddr
    msg['Subject'] = 'CS20 badge for [#{}]'.format(regid)
    msg.set_content(template.render(name=name, warntext=warntext))
    msg.preamble = 'HTML and PDF files are attached, but it seems your email reader is not MIME aware.\n'

    with open(os.path.join(ready_badges, 'badge_{}.pdf'.format(regid)), 'rb') as fp:
            pdf_data = fp.read()
    msg.add_attachment(pdf_data,
                       filename='abstract.pdf',
                       maintype='application', subtype='pdf')
    return msg


def prepare_badge_email(c, regid, warntext=''):
    if not test_regid_known(c, regid):
        raise ValueError('regid {} unknown'.format(regid))

    c.execute('SELECT * FROM badges WHERE regid=?', [str(regid)])
    regid, name, affil, image, emailaddr = c.fetchone()
    if image == 'default':
        image = default_image
    if affil == '':
        affil = 'affiliation here'
    compile_pdf(regid, {'image': image, 'name': name, 'inst': affil,
                        'warntext': warntext})
    return compose_email(emailaddr, regid, name)


def email_for_regids(c, regids):
    send_emails([prepare_badge_email(c, r) for r in regids])


def retrieve_new_messages():
    messagelist = []
    with imaplib.IMAP4_SSL('imap.gmail.com') as imapSession:
        typ, accountDetails = imapSession.login('coolstarsbot@gmail.com', password)
        if typ != 'OK':
            raise Exception('Not able to sign in!')
        imapSession.select('Inbox')
        typ, data = imapSession.search(None, 'unseen')
        if typ != 'OK':
            raise Exception('Error searching Inbox.')
        for msgId in data[0].split():
            typ, messageParts = imapSession.fetch(msgId, '(RFC822)')
            if typ != 'OK':
                raise Exception('Error fetching mail.')
            messagelist.append(messageParts)
    return messagelist


def process_new_messages(conn, c, messages):
    for messageParts in messages:
        emailBody = messageParts[0][1]
        mail = email.message_from_bytes(emailBody)
        match = reg_subject.search(mail['SUBJECT'])
        if match is None:
            # Header does not have message ID in it -> forward to Moritz
            mail.replace_header('From', 'coolstarsbot@gmail.com')
            mail.replace_header('To', 'hgunther@mit.edu')
            send_emails([mail])
        else:
            regid = match['id']
            if not test_regid_known(c, regid):
                mail.replace_header('From', 'coolstarsbot@gmail.com')
                mail.replace_header('To', 'hgunther@mit.edu')
                send_emails([mail])
            else:
                image, warntext = find_first_suitable_image(regid, mail)
                name, inst = find_name_inst(regid, mail)
                if image is not None:
                    c.execute('UPDATE badges SET image=? WHERE regid=?', (image, regid))
                if name is not None:
                    c.execute('UPDATE badges SET name=? WHERE regid=?', (name, regid))
                if inst is not None:
                    c.execute('UPDATE badges SET affil=? WHERE regid=?', (inst, regid))
                conn.commit()
                msg = prepare_badge_email(c, regid, warntext)
                send_emails([msg])


if __name__ == '__main__':
    # set up sqlite
    messages = retrieve_new_messages()
    with sqlite3.connect(os.path.join(selfpath, 'badges.db')) as conn:
        c = conn.cursor()
        process_new_messages(conn, c, messages)
