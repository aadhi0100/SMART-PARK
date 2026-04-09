# 📧 Email Configuration for Render Deployment

## Quick Setup for Render

### 1. Gmail App Password Setup
1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate App Password**:
   - Go to [Google Account Settings](https://myaccount.google.com/)
   - Security → 2-Step Verification → App passwords
   - Select "Mail" and generate password
   - Copy the 16-character password (no spaces)

### 2. Render Environment Variables
Set these in your Render dashboard:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-16-character-app-password
SECRET_KEY=your-secret-key-here
APP_BASE_URL=https://your-app-name.onrender.com
```

### 3. Test Email Configuration
After deployment, visit: `https://your-app.onrender.com/booking/email_manager/admin`

## Troubleshooting Email Issues

### Common Problems & Solutions

#### 1. "Authentication Failed" Error
**Cause**: Wrong SMTP credentials
**Solution**: 
- Use Gmail App Password (not regular password)
- Ensure 2FA is enabled on Gmail
- Double-check SMTP_USER and SMTP_PASS

#### 2. "Connection Timeout" Error
**Cause**: Network/firewall issues
**Solution**:
- Render should allow SMTP connections
- Try different SMTP ports: 587 (TLS) or 465 (SSL)
- Check if Gmail is blocking the connection

#### 3. "No Email Received" Issue
**Cause**: Email sent but not delivered
**Solution**:
- Check spam/junk folder
- Verify recipient email address
- Check Gmail "Sent" folder
- Look at application logs

#### 4. "SMTP_USER not configured" Error
**Cause**: Environment variables not set
**Solution**:
- Set all required environment variables in Render
- Restart the service after setting variables
- Check variable names (case-sensitive)

### Alternative Email Providers

#### SendGrid (Recommended for Production)
```
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASS=your-sendgrid-api-key
```

#### Mailgun
```
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=your-mailgun-username
SMTP_PASS=your-mailgun-password
```

#### Outlook/Hotmail
```
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your-email@outlook.com
SMTP_PASS=your-password
```

## Email Features Available

### 1. Welcome Email
- Sent automatically on user registration
- Professional template with branding
- Includes login link

### 2. Booking Confirmation
- Sent immediately after booking
- Includes parking instructions
- QR code for easy access

### 3. Invoice Email
- Detailed payment receipt
- Professional invoice format
- Downloadable PDF option

### 4. Reminder Emails
- Parking expiry notifications
- Upcoming session reminders
- Custom reminder types

### 5. Monthly Summary
- Usage statistics
- Spending breakdown
- Loyalty points summary

## Testing Email Functionality

### 1. Manual Test
```bash
# Visit the email management page
https://your-app.onrender.com/booking/email_manager/admin

# Click "Send Test Email"
# Check your inbox (and spam folder)
```

### 2. API Test
```bash
curl -X POST https://your-app.onrender.com/booking/email/test/admin \
  -H "Content-Type: application/json"
```

### 3. Check Logs
```bash
# In Render dashboard, check application logs for:
# [Email] Successfully sent "..." to ...
# [Email] Authentication failed ...
# [Email] Failed to send ...
```

## Production Recommendations

### 1. Use Professional Email Service
- **SendGrid**: 100 emails/day free
- **Mailgun**: 5,000 emails/month free
- **Amazon SES**: $0.10 per 1,000 emails

### 2. Email Best Practices
- Use dedicated sending domain
- Set up SPF, DKIM, DMARC records
- Monitor bounce rates
- Implement email templates

### 3. Monitoring
- Set up email delivery monitoring
- Track open rates and clicks
- Monitor for spam complaints
- Regular testing of email functionality

## Environment Variables Reference

### Required for Email
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

### Optional
```
APP_BASE_URL=https://your-app.onrender.com
FROM_NAME=SmartPark
EMAIL_TIMEOUT=60
MAX_EMAIL_RETRIES=3
```

## Support

If emails still don't work:

1. **Check Render Logs**: Look for email-related errors
2. **Test SMTP Settings**: Use an SMTP testing tool
3. **Verify Gmail Settings**: Ensure app passwords are enabled
4. **Contact Support**: Render support for network issues

---

**💡 Pro Tip**: Start with Gmail for testing, then switch to a professional email service like SendGrid for production use.