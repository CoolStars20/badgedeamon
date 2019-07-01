import os
import smtplib
import subprocess
import shutil
from tempfile import TemporaryDirectory
from email.message import EmailMessage
import re
import sqlite3
import imaplib
import email
import email.header
import configparser
import argparse

from jinja2 import Environment, FileSystemLoader


def setup_config_env(configfile):
    '''Read config file and setup jinja2 environment

    Parameters
    ----------
    configfile : string
        path and filename to the configuration file

    Returns
    -------
    config : `configparser.ConfigParser`
        Config parser object
    env : `jinja2.Environment`
        jinja2 Environment
    '''
    config = configparser.ConfigParser()
    config.read(configfile)
    # set up jinja
    env = Environment(loader=FileSystemLoader([config['path']['templates']]))
    return config, env


def regid_known(c, regid):
    c.execute('SELECT COUNT(*) FROM badges WHERE regid = ?', [str(regid)])
    return c.fetchone()[0] == 1


def clean_tex(tex, config):
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

    maxlen = int(config['settings']['max_tex_len'])
    if len(tex) > maxlen:
        return None, 'For security reaons, each field can only contain {} characters (incl. LaTeX markup)- yours is longer: {}. And besides, there is not that much space on the badge anyway. Contact us by email is there really is no way to fit your text into those character limits.'.format(maxlen, tex)

    return tex, ''


def reglist_emailparsing(config):
    return [re.compile(s, re.IGNORECASE) for s in config['email parsing'].values()]


def find_text_part(msg):
    textplain = None
    texthtml = None
    for part in msg.walk():
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
                # tags can remain, but that's not a security risk for
                # this application
                # re.sub('<[^<]+?>', '', texthtml)
                # texthtml = texthtml.splitlines()
    if (textplain is None) and (texthtml is None):
        return None
    else:
        text = texthtml if (textplain is None) else textplain
        charset = text.get_content_charset()
        text = text.get_payload(decode=True)
        return text.decode(charset).splitlines()


def parse_text(text, config):
    regs = reglist_emailparsing(config)

    warntext = []
    parsedvalues = {}
    # look for first occurrence in text.
    # Later lines are most likely just the old message attached at bottom
    text.reverse()
    for l in text:
        for r in regs:
            match = r.search(l)
            if match:
                parsedvalues.update(match.groupdict())
    cleanvalues = {}
    for k, v in parsedvalues.items():
        # The following line is for the obscure case that a regex
        # has optional named groups and only some of them are
        # matched. In this case, the remaining ones have value
        # "None" which might cause problems further down.
        if v is not None:
            newval, newwarn = clean_tex(v, config)
            if newval is not None:  # valid
                cleanvalues[k] = newval
            else:  # invalid tex value
                warntext.append(newwarn)
    return cleanvalues, '\n'.join(warntext)


def find_firstsecond_suitable_image(regid, mail, config):
    image = [None, None]
    warntext = ''
    for part in mail.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue
        fileName = part.get_filename()
        if bool(fileName):
            extension = fileName.split('.')[-1]
            if extension.lower() not in ['jpg', 'jpeg', 'png', 'pdf']:
                continue
            else:
                if image[0] is None:
                    fullfilename = regid + '_front.' + extension
                    filePath = os.path.join(config['path']['image_dir'], fullfilename)
                    with open(filePath, 'wb') as fp:
                        fp.write(part.get_payload(decode=True))
                    image[0] = fullfilename
                elif image[1] is None:
                    fullfilename = regid + '_back.' + extension
                    filePath = os.path.join(config['path']['image_dir'], fullfilename)
                    with open(filePath, 'wb') as fp:
                        fp.write(part.get_payload(decode=True))
                    image[1] = fullfilename

                else:
                    warntext = "More than two image files were attached to your message. I'm using the first and second of those for your badge.\n"
    if image[0] is None:
        warntext = "No file ending on 'jpg', 'jpeg', 'pdf', or 'png' was attached to your email. I'm using whatever file you previously submitted or (if you did not submit a file with a previous email) a default image.\n"
    return image, warntext


def compile_pdf(dat, config, env):
    template = env.get_template(config['templates']['tex'])
    regid = dat['regid']
    with TemporaryDirectory() as tempdir:
        with open(os.path.join(tempdir, 'badge_{}.tex'.format(regid)), "w") as tex_out:
            tex_out.write(template.render(data=dat))
        for fname in config['templates']['extra_files'].split():
            shutil.copy(os.path.join(config['path']['templates'], fname), tempdir)
        shutil.copy(os.path.join(config['path']['image_dir'], dat['image1']), tempdir)
        shutil.copy(os.path.join(config['path']['image_dir'], dat['image2']), tempdir)
        latex = subprocess.Popen(['pdflatex', '-interaction=nonstopmode',
                                  '-no-shell-escape',
                                  'badge_{}.tex'.format(regid)],
                                 cwd=tempdir,
                                 stdout=subprocess.PIPE)
        out, err = latex.communicate()
        shutil.copy(os.path.join(tempdir, 'badge_{}.pdf'.format(regid)),
                    config['path']['badge_dir'])
        shutil.copy(os.path.join(tempdir, 'badge_{}.tex'.format(regid)),
                    config['path']['badge_dir'])


def compose_email(data, config, env, warntext=''):
    template = env.get_template(config['templates']['email'])
    # Create the container email message.
    msg = EmailMessage()
    msg['From'] = config['email']['address']
    msg['To'] = data['email']
    print('Composing email to: {}'.format(data['email']))
    msg['Subject'] = config['email subject']['subject'].format(data['regid'])
    msg.set_content(template.render(data=data, warntext=warntext))
    msg.preamble = 'PDF file is attached, but it seems your email reader is not MIME aware.\n'

    with open(os.path.join(config['path']['badge_dir'], 'badge_{}.pdf'.format(data['regid'])), 'rb') as fp:
            pdf_data = fp.read()
    msg.add_attachment(pdf_data,
                       filename='badge.pdf',
                       maintype='application', subtype='pdf')
    return msg


def data_for_regid(c, regid, config):
    if not regid_known(c, regid):
        raise ValueError('regid {} unknown'.format(regid))
    c.execute('SELECT * FROM badges WHERE regid=?', [str(regid)])
    row = c.fetchone()
    data = {c.description[i][0]: row[i] for i in range(len(row))}
    if 'role' in data.keys():
        # defauls to black is role is not in config
        data['rolecolor'] = config['color'].get(data['role'], 'black')
        data['rolecolortext'] = config['colortext'].get(data['role'], 'white')
    return data


def prepare_pdf(c, regid, config, env):
    data = data_for_regid(c, regid, config)
    compile_pdf(data, config, env)


def prepare_badge_email(c, regid, config, env, warntext=''):
    data = data_for_regid(c, regid, config)
    compile_pdf(data, config, env)
    msg = compose_email(data, config, env, warntext)
    return msg


def send_emails(msg, config):
    with smtplib.SMTP(config['email']['smtp_server'],
                      config.getint('email', 'smtp_port')) as s:
        s.ehlo()
        s.starttls()
        s.login(config['email']['address'], config['email']['password'])
        for m in msg:
            s.send_message(m)


def email_for_regids(c, regids, config, env):
    send_emails([prepare_badge_email(c, r, config, env) for r in regids], config)


def retrieve_new_messages(config):
    messagelist = []
    with imaplib.IMAP4_SSL(config['email']['imap_server']) as imapSession:
        typ, accountDetails = imapSession.login(config['email']['address'],
                                                config['email']['password'])
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
        print('Retrieved {} messages.'.format(len(messagelist)))
    return messagelist


def forward_email(mail, config):
    mail.replace_header('From', config['email']['address'])
    mail.replace_header('To', config['email']['alert'])
    send_emails([mail], config)


def parse_message(conn, c, regid, mail, config):
    '''Parse a single message for text and attachements  and update sql database'''
    image, warntext = find_firstsecond_suitable_image(regid, mail, config)
    text = find_text_part(mail)
    parsedvalues, warntext2 = parse_text(text, config)
    if image[0] is not None:
        # If only one image is submitted, use that for both sides
        if image[1] is None:
            image[1] = image[0]
        c.execute('UPDATE badges SET image1=? WHERE regid=?', (image[0], regid))
        c.execute('UPDATE badges SET image2=? WHERE regid=?', (image[1], regid))
    for k, v in parsedvalues.items():
        # Note that format(k) is not a security issue because the keys are
        # defined by the person setting up script in the configuration
        # and not by the sender of the email
        c.execute('UPDATE badges SET {}=? WHERE regid=?'.format(k), (v, regid))
    conn.commit()
    return warntext + ' ' + warntext2


def process_new_messages(conn, c, messages, config, env):
    reg_subject = re.compile(config['email subject']['reg_subject'], re.IGNORECASE)

    for messageParts in messages:
        emailBody = messageParts[0][1]
        mail = email.message_from_bytes(emailBody)
        subject = mail['SUBJECT']
        # Header may as characters that are utf-8 formated
        dh = email.header.decode_header(mail['SUBJECT'])
        dsubject = ''.join([ t[0].decode(t[1] or 'ASCII') for t in dh ])
        match = reg_subject.search(dsubject)
        if (match is None) or not regid_known(c, match.groups('id')[0]):
            # Header does not have message ID in it
            forward_email(mail, config)
        else:
            regid = match.groups('id')[0]
            warntext = parse_message(conn, c, regid, mail, config)
            msg = prepare_badge_email(c, regid, config, env, warntext)
            send_emails([msg], config)

class DeamonTableException(Exception):
    '''Exception class for all table errors that are explicitly tested in this code.'''
    pass


def check_input_table(c, config):
    '''Check that table "badges" exists and has the required columns.

    This script has a few requirements on the name of the table that holds the
    information about the badges and its columns. Some of this stuff can be
    customized in the configuation file, but not all of it.

    This message simply performs some simple, non-exhaustive checks on the
    table and prints meaningful error messages.
    '''
    c.execute("select count(*) from sqlite_master where type='table' and name='badges'")
    if not c.fetchone()[0] == 1:
        raise DeamonTableException('Table "badges" does not exist in the database file.')
    c.execute('SELECT * FROM badges')
    colnames = [description[0] for description in c.description]
    col_names_requd = ['regid', 'image1', 'image2', 'email']
    if not set(col_names_requd) <= set(colnames):
        raise DeamonTableException('Columns {} are required in table "badges" but {} found.'.format(col_names_requd, colnames))

    regs = reglist_emailparsing(config)
    for r in regs:
        colset = set(r.groupindex.keys())
        if not colset <= set(colnames):
            raise DeamonTableException('The regular expression {} defines the groups {}, but not all of them correspond to columns in table "badges".'.format(r.pattern, colset))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download new emails, process them, update badge database and send out updated badges.')
    parser.add_argument('config', type=argparse.FileType('r'),
                        help='configuration file')

    args = parser.parse_args()
    config, env = setup_config_env(args.config.name)

    # set up sqlite
    dbpath = config['path']['sql_database']
    if not os.path.exists(dbpath):
        raise DeamonTableException('Database file {} does not exist.'.format(dbpath))

    with sqlite3.connect(dbpath) as conn:
        c = conn.cursor()
        check_input_table(c, config)
        messages = retrieve_new_messages(config)
        process_new_messages(conn, c, messages, config, env)
