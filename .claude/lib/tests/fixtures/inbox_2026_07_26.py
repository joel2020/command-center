"""42 real threads from Joel's inbox, 2026-07-26, with hand-assigned buckets.

Captured from the live Gmail connector during the session that populated the
project list. Senders and subjects are verbatim; snippets are truncated to the
part that carries signal.

This fixture exists because the classifier was measured against it and scored
0/11 precision and 0/3 recall on ACT. Every ACT it produced was a newsletter,
and all three genuinely actionable messages were filed as NOISE or FYI. Any
change to triage.py runs against this and has to keep the score.

`expected` is the bucket Joel would assign. Where a message is defensibly
either FYI or NOISE the label leans FYI, because the cost of over-filing is
higher than the cost of one extra line in the evening digest.
"""

# (sender, subject, snippet, expected_bucket)
THREADS = [
    # ---- the three that actually matter -------------------------------------
    ("voice-noreply@google.com",
     "New voicemail from (650) 215-5641",
     "Your Apple account confirmation request was confirmed on an iPhone 16 from "
     "the location of Baghdad Iraq If this was not you press one on your keypad",
     "ACT"),
    ("googleone-noreply@google.com",
     "⚠️ Your Google One storage is 87% full",
     "Learn what happens if you run out of storage",
     "ACT"),
    ("info@opticgold.com",
     "Appointment Scheduled: Optic Gold",
     "Hi Joel Carias, Please mark your calendar, you are scheduled with "
     "DR MICHELLE SANSEVERINO on Wednesday 7/29/2026 at 10:00 am.",
     "ACT"),

    # ---- real information, no action ----------------------------------------
    ("suracomunicaciones@sura.com.co",
     "890903790;SEGUROS DE VIDA SURAMERICANA S.A;20006977817;91",
     "En SURA queremos brindarte informacion oportuna, te invitamos a abrir los "
     "archivos adjuntos, donde encuentras la nota credito electronica",
     "FYI"),
    ("noreply-accounts@google.com",
     "You shared some Google Account data with Dragonpass",
     "You're receiving this email because you used Sign in with Google to sign in "
     "to Dragonpass on July 26 at 3:44 PM.",
     "FYI"),
    ("info@myiclubonline.com",
     "Your new agreement",
     "Here is a copy of your agreement for your records. New Agreement 3231000544",
     "FYI"),
    ("noreply@trainerize.com",
     "Welcome to Elev8tion Fitness",
     "Before you can sign in to Elev8tion, you must set up your password.",
     "FYI"),
    ("info@email.prioritypass.com",
     "Welcome to Priority Pass",
     "Congratulations, your Priority Pass membership is active.",
     "FYI"),

    # ---- bulk senders that previously escaped detection --------------------
    # Every one of these was classified ACT. They are the false-positive set.
    ("adidas@us-news.comms.adidas.com",
     "New adidas | Care Bears collection",
     "Full of bold color and feel-good comfort. Display images to show real-time content",
     "NOISE"),
    ("prioritypass@safeopt.com",
     "Your recent visit unlocked an exclusive offer.",
     "Save today at Priority Pass Activate 25% off + $10 back",
     "NOISE"),
    ("inspiration@mp1.tripadvisor.com",
     "5 of Europe's coolest beaches",
     "Plus, where to keep the soccer energy going.",
     "NOISE"),
    ("Coursera@m.learn.coursera.org",
     "Don't miss 3 months of Google AI Pro at no extra cost",
     "Enroll in any Google Career Certificate and start learning with AI",
     "NOISE"),
    ("email@e.upgrade.com",
     "Get ahead of your monthly payments",
     "New loan invitation inside, Joel",
     "NOISE"),
    ("email@savings.lendingtree.com",
     "Joel, finish your personal loan search",
     "Resume in one click.",
     "NOISE"),
    ("info@myiclubonline.com",
     "MYiCLUBonline Registration",
     "Thank you for becoming a member of Elev8tion Fitness Aventura. Did you know "
     "you can manage your new account online?",
     "NOISE"),

    # ---- ordinary noise ----------------------------------------------------
    ("notifications-noreply@linkedin.com",
     "You have 5 new invitations", "See who reached out, Joel", "NOISE"),
    ("donotreply@jobalert.indeed.com",
     "account executive in New York, NY: Sales Development Representative and 29 more new jobs",
     "$6000 - $8000 a month", "NOISE"),
    ("info@e.equifax.com",
     "It's time to check your credit scores, Joel",
     "Get your scores from all 3 credit bureaus", "NOISE"),
    ("ebay@ebay.com",
     "Apple MacBook Air 1 is in demand",
     "Make it yours before someone else does", "NOISE"),
    ("events@mail.stubhub.com",
     "Liverpool FC and more picks for you",
     "View upcoming events picked just for you", "NOISE"),
    ("hello@email.rocketmoney.com",
     "Let's start reducing your spending",
     "Here's where you should get started", "NOISE"),
    ("alerts@account.seeking.com",
     "Profile has been favorited", "2 members recently favorited you", "NOISE"),
    ("alerts@account.seeking.com",
     "Tami sent you a message", "see what they had to say!", "NOISE"),
    ("alerts@account.seeking.com",
     "Check out the newest members in your area!",
     "6 members recently favorited you!", "NOISE"),
    ("noreply@skool.com",
     "2 new notifications since 1:26 pm",
     "LetsGetFunded Starter Evan Rugen posted", "NOISE"),
    ("noreply@skool.com",
     "James Blackwell posted \"What Making My First Million Taught Me About Freedom\"",
     "Automatic Recruitment Agency James Blackwell created a new post", "NOISE"),
    ("noreply@skool.com",
     "1 event happening tomorrow",
     "Community Onboarding Monday, July 27th 3:00pm Bogota time", "NOISE"),
    ("noreply@skool.com",
     "Weekly digest for Wed, Jul 15 2026",
     "Automatic Recruitment Agency Weekly Digest James Blackwell", "NOISE"),
    ("editors-noreply@linkedin.com",
     "Employers turn to 'backdoor references'",
     "The controversial method used to be reserved for senior roles", "NOISE"),
    ("newsletters-noreply@linkedin.com",
     "The Team that Goes Quiet",
     "A CEO I worked with ran a good meeting", "NOISE"),
    ("careerbrew@substack.com",
     "Career Brew - 54 Hottest Early to Mid Career Jobs",
     "$136K at Akamai; $120K at Traackr", "NOISE"),
    ("donotreply@match.indeed.com",
     "Care Team Advisor - Entry Sales at Senior Proof Inc. and 10 more new jobs",
     "Your background in recruiting could be a great foundation", "NOISE"),
    ("instructors@updates.freeletics.com",
     "Hydrate happy with these 5 mocktails",
     "Get stirred not shaken with these hydrating mocktails", "NOISE"),
    ("notification@service.tiktok.com",
     "sn_sushrii: Which look did you like the most?",
     "6.9K+ people liked the video.", "NOISE"),
    ("alerts@ziprecruiter.com",
     "Joel, UniFirst has an open position", "", "NOISE"),
    ("news@e.sunglasshut.com",
     "Hey Meta, como puedo aduenarme de cada momento este verano?",
     "Los lentes con IA son la respuesta.", "NOISE"),
    ("jobalert@lensa.com",
     "Employer Posted Recruiter Job Leads You Should Apply to Now",
     "New York Institute of Technology and US Secret Service are hiring now", "NOISE"),
    ("remy@mail.aiwithremy.com",
     "your AI agents can finally work as a team",
     "meet BUZZ, the Slack for AI agents", "NOISE"),
    ("noreply@polymarket.com",
     "TACO Tuesday comes early?",
     "Welcome back to your daily mind meld with the Polymarket order book", "NOISE"),
    ("superhuman@mail.joinsuperhuman.ai",
     "✈️ Lost plane found after 70 years",
     "Orcas are called killer whales for a reason", "NOISE"),
    ("newsletter@expatmoney.com",
     "Get Your Coffee Ready!",
     "We're live in just two hours to discuss our expansion plans into Costa Rica",
     "NOISE"),

    # The one residual false positive, and it is expected.
    #
    # A newsletter from a person's own domain: no bulk local part, no mail
    # subdomain, brand name absent from the address, and Joel has never written
    # back. It is indistinguishable from a real first-time human without
    # reading the List-Unsubscribe header.
    #
    # email-rules.md says "any first-time human sender" is ACT regardless of
    # what the classifier believes. That is Joel's rule, so ACT is the correct
    # output here, not a bug to code around. The designed remedy is a
    # correction line, which outranks every heuristic:
    #
    #   - 2026-07-26 | domain:patrickdang.com | NOISE | paid newsletter
    ("pd@patrickdang.com",
     "the future of ai",
     "Hey Joel, People wonder what the future of work will look like once AI "
     "gets better. From my point of view, we're just in the early stages",
     "ACT"),
]


def messages():
    return [{"sender": s, "subject": su, "snippet": sn} for s, su, sn, _ in THREADS]


def expected():
    return [e for _, _, _, e in THREADS]
