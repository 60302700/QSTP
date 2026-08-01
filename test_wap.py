from whatsapp_message import send_whatsapp_message

startup_phone = candidate_phone = '+974 50827742'
candidate_name = 'Fathima'
job_title = 'Software Engineer'
startup_name = 'Quantum AI'


# Message to the candidate
send_whatsapp_message(
    candidate_phone,
    f"""Hi {candidate_name}! 🎉

You've been shortlisted for the {job_title} position at {startup_name}.

We'll be in touch with the next steps soon.

This is an automated message. Please do not reply."""
)

# Message to the startup
send_whatsapp_message(
    startup_phone,
    f"""Hi {startup_name}! 👋

A candidate has been shortlisted for your {job_title} position.

Please check your dashboard to review the shortlisted candidate and continue the hiring process.

This is an automated message. Please do not reply."""
)