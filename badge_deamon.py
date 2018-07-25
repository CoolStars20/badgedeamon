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
reg_newpronoun = re.compile('BADGE PRONOUN:(?P<pronoun>[\S\s]+)', re.IGNORECASE)
reg_newname = re.compile('BADGE NAME:(?P<name>[\S\s]+)', re.IGNORECASE)
reg_newaffiliation = re.compile('BADGE AFFILIATION:(?!Institute of Example)(?P<affil>[\S\s]+)', re.IGNORECASE)
badge_images = '/melkor/d1/guenther/projects/cs20/badgeimages'
ready_badges = '/melkor/d1/guenther/projects/cs20/badges/'
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


def clean_tex(tex, maxlen=45):
    '''LaTeX can be used to execute arbitrary commands.
    While a full sanatizing might be impossible, we use an approach here that
    blacklists the most dangerous commands AND puts a very restrictive length requirement
    on the string. All blacklists can be circumvented, but that requires a number
    of commands and should not be possible within 30 characters or so.

    see: https://0day.work/hacking-with-latex/
    '''
    blacklist = ['input', 'include', 'write18', 'immediate', 'def']
    for b in blacklist:
        if '\\' + b in tex:
            return None, 'For security reasons LaTeX command {} is disabled in this script. Contact us by email if you really need it for your badge.'.format(b)

    if len(tex) > maxlen:
        return None, 'For security reaons, each field of can only contain {} characters (incl. LaTeX markup)- yours is longer: {}. And besides, there is not that much space on the badge anyway. Contact us by email is there really is no way to fit your text into those character limits.'.format(maxlen, tex)

    return tex.replace('=20', '').replace('=0A', ''), ''


def find_pronoun_name_inst(regid, mail):
    textplain = None
    texthtml = None
    name = None
    affil = None
    for part in mail.walk():
        if part.get_content_maintype() == 'text':
            if part.get_content_subtype() == 'plain':
                textplain = part
                # Hack. Should probably have better code that deals with email
                # that have several text/plain parts.
                # Usually, the important one if the first one, but I probably
                # should parse all of them.
                break
            if part.get_content_subtype() == 'html':
                texthtml = part
                # Remove obvious html tags. This method can be fooled and html
                # tags and remain, but that's not a security risk for
                # this application
                # re.sub('<[^<]+?>', '', texthtml)
                # texthtml = texthtml.splitlines()
    if (textplain is None) and (texthtml is None):
        return None, None
    else:
        text = texthtml if (textplain is None) else textplain
        charset = text.get_content_charset()
        text = text.get_payload(decode=True).splitlines()
        wtext1 = ''
        wtext2 = ''
        wtext0 = ''
        pronoun = None
        name = None
        affil = None
        # look for first occurrence in text.
        # Later lines are most likely just the old message attached at bottom
        text.reverse()
        for l in text:
            # I think the type of l is always bytes due to the decode=True above
            # but since this program is live already, I'll rather add another test
            # to be sure
            if type(l) is bytes:
                l = l.decode(charset)
            p = reg_newpronoun.search(l)
            m = reg_newname.search(l)
            a = reg_newaffiliation.search(l)
            if p is not None:
                pronoun = p['pronoun']
                pronoun, wtext0 = clean_tex(pronoun)
            if m is not None:
                name = m['name']
                name, wtext1 = clean_tex(name)
            if a is not None:
                affil = a['affil']
                affil, wtext2 = clean_tex(affil)
        return pronoun, name, affil, wtext0 + wtext1 + wtext2


def find_firstsecond_suitable_image(regid, mail):
    image = [None, None]
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
                if image[0] is None:
                    fullfilename = regid + '_front.' + extension
                    filePath = os.path.join(badge_images, fullfilename)
                    with open(filePath, 'wb') as fp:
                        fp.write(part.get_payload(decode=True))
                    image[0] = fullfilename
                elif image[1] is None:
                    fullfilename = regid + '_back.' + extension
                    filePath = os.path.join(badge_images, fullfilename)
                    with open(filePath, 'wb') as fp:
                        fp.write(part.get_payload(decode=True))
                    image[1] = fullfilename

                else:
                    warntext = "More than two images file were attached to your message. I'm using the first and second of those for your badge.\n"
    if image[0] is None:
        warntext = "No file ending on 'jpg', 'jpeg' or 'png' was attached to your email. I'm using whatever file you previously submitted or (if you did not submit a file with a previous email) a default image.\n"
    return image, warntext


def compile_pdf(regid, dat):
    template = env.get_template('badge_template.tex')
    with TemporaryDirectory() as tempdir:
        with open(os.path.join(tempdir, 'badge_{}.tex'.format(regid)), "w") as tex_out:
            tex_out.write(template.render(dat=dat))
        shutil.copy(os.path.join(selfpath, 'csheader.jpg'), tempdir)
        shutil.copy(os.path.join(selfpath, 'csheader_narrow.jpg'), tempdir)
        shutil.copy(os.path.join(badge_images, dat['image1']), tempdir)
        shutil.copy(os.path.join(badge_images, dat['image2']), tempdir)
        latex = subprocess.Popen(['pdflatex', '-interaction=nonstopmode',
                                  '-no-shell-escape',
                                  'badge_{}.tex'.format(regid)],
                                 cwd=tempdir,
                                 stdout=subprocess.PIPE)
        out, err = latex.communicate()
        shutil.copy(os.path.join(tempdir, 'badge_{}.pdf'.format(regid)),
                    ready_badges)
        shutil.copy(os.path.join(tempdir, 'badge_{}.tex'.format(regid)),
                    ready_badges)


def compose_email(emailaddr, regid, pronoun, name, affil, warntext=''):
    template = env.get_template('email_template.txt')
    # Create the container email message.
    msg = EmailMessage()
    msg['From'] = 'coolstarsbot@gmail.com'
    msg['To'] = emailaddr
    msg['Subject'] = 'CS20 badge for [#{}]'.format(regid)
    msg.set_content(template.render(pronoun=pronoun, name=name, affil=affil, warntext=warntext))
    msg.preamble = 'HTML and PDF files are attached, but it seems your email reader is not MIME aware.\n'

    with open(os.path.join(ready_badges, 'badge_{}.pdf'.format(regid)), 'rb') as fp:
            pdf_data = fp.read()
    msg.add_attachment(pdf_data,
                       filename='badge.pdf',
                       maintype='application', subtype='pdf')
    return msg


def prepare_badge_email(c, regid, warntext=''):
    if not test_regid_known(c, regid):
        raise ValueError('regid {} unknown'.format(regid))

    c.execute('SELECT * FROM badges WHERE regid=?', [str(regid)])
    regid, pronoun, name, affil, image1, image2, emailaddr, title = c.fetchone()
    if affil == '':
        affil = 'affiliation here'
    if title == 'LOC':
        color = 'green'
    elif title == 'SOC':
        color = 'blue'
    elif title == "Press":
        color = 'red'
    else:
        color = 'black'
    print('Preparing email for: {}'.format(name))
    compile_pdf(regid, {'image1': image1, 'image2': image2, 'pronoun': pronoun,
                        'name': name, 'inst': affil,
                        'typetext': title, 'typecolor': color})
    return compose_email(emailaddr, regid, pronoun, name, affil, warntext)


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
                image, warntext = find_firstsecond_suitable_image(regid, mail)
                pronoun, name, inst, warntext2 = find_pronoun_name_inst(regid, mail)
                if image[0] is not None:
                    # If only one image is submitted, use that for both sides
                    if image[1] is None:
                        image[1] = image[0]
                    c.execute('UPDATE badges SET image1=? WHERE regid=?', (image[0], regid))
                    c.execute('UPDATE badges SET image2=? WHERE regid=?', (image[1], regid))
                if pronoun is not None:
                    c.execute('UPDATE badges SET pronoun=? WHERE regid=?', (pronoun, regid))
                if name is not None:
                    c.execute('UPDATE badges SET name=? WHERE regid=?', (name, regid))
                if inst is not None:
                    c.execute('UPDATE badges SET affil=? WHERE regid=?', (inst, regid))
                conn.commit()
                msg = prepare_badge_email(c, regid, warntext + ' ' + warntext2)
                send_emails([msg])


if __name__ == '__main__':
    # set up sqlite
    messages = retrieve_new_messages()
    with sqlite3.connect(os.path.join(selfpath, 'badges.db')) as conn:
        c = conn.cursor()
        process_new_messages(conn, c, messages)
