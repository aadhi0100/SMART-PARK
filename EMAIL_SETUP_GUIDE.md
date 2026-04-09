# 📧 SmartPark Email Configuration Guide

## Quick Setup for Gmail

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate App Password**:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. **Update .env file**:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASS=your-16-digit-app-password
   ```

## Other Email Providers

### Outlook/Hotmail
```
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your-email@outlook.com
SMTP_PASS=your-password
```

### Yahoo Mail
```
SMTP_HOST=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USER=your-email@yahoo.com
SMTP_PASS=your-app-password
```

### Custom SMTP
```
SMTP_HOST=your-smtp-server.com
SMTP_PORT=587
SMTP_USER=your-email@domain.com
SMTP_PASS=your-password
```

## Testing Email Configuration

1. Start the server: `start_enhanced.bat`
2. Go to: `http://localhost:5003/booking/email_manager/admin`
3. Click "Send Test Email"
4. Check your email inbox

## Email Features

### 🎯 Automatic Emails
- **Booking Confirmation**: Sent immediately after booking
- **Invoice**: Professional invoice with QR code
- **Reminders**: Parking expiry notifications
- **Monthly Summary**: Usage statistics

### 📊 Email Types
1. **Welcome Email**: New user registration
2. **Booking Confirmation**: Immediate confirmation
3. **Invoice Email**: Detailed payment receipt
4. **Reminder Emails**: Upcoming/expiring/expired
5. **Monthly Summary**: Statistics and insights
6. **Promotional**: Special offers and updates

### 🔧 Management Features
- Test email functionality
- Resend invoices for any booking
- Send monthly summaries on demand
- Custom reminder emails
- Bulk email capabilities

## Troubleshooting

### Common Issues

1. **"Authentication failed"**
   - Check SMTP_USER and SMTP_PASS
   - For Gmail, use App Password (not regular password)
   - Ensure 2FA is enabled for Gmail

2. **"Connection timeout"**
   - Check SMTP_HOST and SMTP_PORT
   - Verify firewall/antivirus settings
   - Try different port (465 for SSL)

3. **"Recipient refused"**
   - Check email address format
   - Verify recipient email exists
   - Check spam folder

### Advanced Configuration

#### SSL/TLS Settings
For secure connections, you can modify the email settings:
- Port 465: SSL
- Port 587: TLS (recommended)

#### Rate Limiting
The system includes automatic retry logic:
- 3 retry attempts
- 2-second delay between retries
- Exponential backoff for failures

## Security Best Practices

1. **Use App Passwords**: Never use your main email password
2. **Environment Variables**: Keep credentials in .env file
3. **Regular Updates**: Update passwords periodically
4. **Monitor Logs**: Check email sending logs regularly

## Email Templates

All email templates are responsive and professional:
- Mobile-friendly design
- Brand consistent styling
- QR codes for easy access
- Clear call-to-action buttons
- Professional formatting

## Support

If you need help with email configuration:
1. Check the logs in the console
2. Use the email test feature
3. Verify your email provider settings
4. Contact your email provider for SMTP details

---

**Note**: Keep your .env file secure and never commit it to version control!