import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread
import os
from ..config import app_config

sender = app_config.EMAIL
password = app_config.PASSWORD
mail_server = app_config.MAIL_SERVER

def email_default_setup():
	context = ssl.create_default_context()
	server = smtplib.SMTP_SSL(mail_server, 465, context=context)
	server.login(sender, password)
	return server 


def send_email(subject, sender, receiver, text_body, html_body):
	server = email_default_setup()
	message = MIMEMultipart("alternative")
	message["Subject"] = subject
	message["From"] = sender 
	message["To"] = receiver
	text_part = MIMEText(text_body, "plain")
	message.attach(text_part)
	Thread( target=send_async_email, args=(server,sender, receiver, message.as_string()) ).start()
	

def send_async_email(server, sender, receiver, message):
	server.sendmail( sender, receiver, message)
	

def send_password_reset_email( user ):
	otp = user.get_otp() 
	message = "Your request to reset password has been accepted. Your OTP is - " + otp
	send_email( '[BlogStack] Reset Your Password',
		sender=sender,
		receiver=user.email, 
		text_body=message,
		html_body=None
	)

