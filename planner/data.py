"""Static planning knowledge: budget weights, timeline templates, vendor lists, idea banks.

Kept separate from the logic in engine.py so content can be tuned without touching code.
All benchmark numbers are illustrative heuristics (see README, "Assumptions").
"""
from __future__ import annotations

EVENT_TYPES = ("wedding", "birthday", "community")
VENUE_TYPES = ("indoor", "outdoor", "home")
VIBES = ("traditional", "modern", "minimal", "fun")
DIETARY = ("vegetarian", "vegan", "jain", "halal", "gluten_free")
ATTENDEES = ("kids", "seniors")
CURRENCIES = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}

LABELS = {
    "sound_av": "Sound & AV",
    "permits_security": "Permits & security",
    "gifts": "Return gifts",
    "decor": "Decor & flowers",
    "contingency": "Contingency buffer",
}

# Whole-number percentages; every row sums to 100 and contains the keys
# venue, catering, decor, entertainment and contingency (the engine shifts money between them).
BUDGET_WEIGHTS = {
    "wedding": {
        "venue": 30, "catering": 30, "photography": 10, "decor": 8, "attire": 8,
        "entertainment": 5, "invitations": 2, "transport": 2, "contingency": 5,
    },
    "birthday": {
        "venue": 25, "catering": 30, "decor": 12, "entertainment": 13, "cake": 7,
        "gifts": 5, "invitations": 3, "contingency": 5,
    },
    "community": {
        "venue": 20, "catering": 25, "sound_av": 15, "decor": 8, "publicity": 8,
        "permits_security": 7, "entertainment": 7, "volunteers": 5, "contingency": 5,
    },
}

# Minimum comfortable spend per guest, by currency then event type.
MIN_PER_GUEST = {
    "INR": {"wedding": 800, "birthday": 400, "community": 150},
    "USD": {"wedding": 40, "birthday": 20, "community": 8},
    "EUR": {"wedding": 40, "birthday": 20, "community": 8},
    "GBP": {"wedding": 35, "birthday": 18, "community": 7},
}

# (days_before_event, task, category, critical)
TIMELINES = {
    "wedding": [
        (270, "Set the total budget and agree on priorities", "planning", True),
        (270, "Draft the core guest list and an approximate headcount", "planning", True),
        (240, "Shortlist and book the venue", "venue", True),
        (210, "Book photographer and videographer", "photography", True),
        (210, "Book the caterer", "catering", True),
        (180, "Book decorator / florist and share the theme", "decor", False),
        (150, "Order attire and schedule fittings", "attire", False),
        (120, "Book music: DJ, band and emcee", "entertainment", False),
        (120, "Plan guest accommodation and transport", "transport", False),
        (90, "Design and order invitations", "invitations", True),
        (60, "Send invitations and start RSVP tracking", "invitations", True),
        (45, "Menu tasting and final menu", "catering", True),
        (30, "Final fittings and accessories", "attire", False),
        (21, "Confirm every vendor in writing and share the run-of-show", "vendors", True),
        (14, "Lock seating plan and final headcount with the caterer", "catering", True),
        (7, "Pay vendor balances and prepare tips in envelopes", "budget", True),
        (3, "Rehearsal and an emergency kit (safety pins, first aid, chargers)", "logistics", False),
        (1, "Brief day-of coordinators and family helpers", "logistics", True),
        (0, "Event day: follow the run-of-show", "event", True),
    ],
    "birthday": [
        (45, "Set the budget and pick a theme", "planning", True),
        (45, "Draft the guest list", "planning", True),
        (35, "Book the venue or plan the home layout", "venue", True),
        (30, "Book the caterer or restaurant menu", "catering", True),
        (28, "Book entertainer, DJ or game host", "entertainment", False),
        (21, "Send invitations", "invitations", True),
        (14, "Order the cake and decor supplies", "cake", True),
        (10, "Plan games, playlist and return gifts", "gifts", False),
        (7, "Confirm RSVPs and vendors", "vendors", True),
        (3, "Give the caterer the final headcount", "catering", True),
        (1, "Set up decor and prepare food stations", "logistics", False),
        (0, "Party day", "event", True),
    ],
    "community": [
        (60, "Define purpose, audience and budget", "planning", True),
        (55, "Form a volunteer committee and assign roles", "volunteers", True),
        (50, "Apply for permissions (local authority, society, police if needed)", "permits_security", True),
        (45, "Book the venue and sound / AV", "venue", True),
        (40, "Secure sponsors or collect contributions", "budget", False),
        (35, "Book the caterer or arrange food stalls", "catering", True),
        (30, "Start publicity: posters, WhatsApp groups, social media", "publicity", True),
        (21, "Confirm performers or speakers and the programme schedule", "entertainment", True),
        (14, "Plan safety: first aid, crowd flow, parking and waste", "permits_security", True),
        (7, "Confirm vendors and brief volunteers", "vendors", True),
        (3, "Final walkthrough and equipment check", "logistics", True),
        (1, "Set up and run a sound check", "logistics", False),
        (0, "Event day", "event", True),
    ],
}

# category doubles as the budget key whenever a budget line with that name exists.
VENDORS = {
    "wedding": [
        {"category": "venue", "vendor": "Venue / banquet hall", "skip_venue": ("home",),
         "ask": ["Is my date held in writing, and for how long?",
                 "What are the rain and power-backup plans and the overtime rate?",
                 "Are outside caterers and decorators allowed (any corkage or ground fees)?"],
         "contract": ["Total fee, taxes and refundable deposit", "Cancellation and date-change terms"]},
        {"category": "catering", "vendor": "Caterer",
         "ask": ["Can I taste the menu and get a per-plate price for my headcount?",
                 "What is the staff-to-guest ratio, and are crockery and service included?"],
         "contract": ["Final headcount deadline and over/under-count policy", "Menu, quantities and live-counter list"]},
        {"category": "photography", "vendor": "Photographer / videographer",
         "ask": ["How many hours and how many shooters are included?",
                 "When will edited photos and the film be delivered?"],
         "contract": ["Deliverables, delivery dates and raw-file policy", "Backup plan if the photographer is unavailable"]},
        {"category": "decor", "vendor": "Decorator / florist",
         "ask": ["Can you share a mood board and itemised quote for my theme?",
                 "Who handles setup and teardown, and by what time?"],
         "contract": ["Itemised list with quantities", "Substitution policy for flowers"]},
        {"category": "attire", "vendor": "Tailor / boutique / rental",
         "ask": ["What are the fitting dates and the final delivery date?", "What is the alteration and return policy?"],
         "contract": ["Delivery date at least two weeks before the event"]},
        {"category": "entertainment", "vendor": "DJ / band / emcee",
         "ask": ["Can you share a sample setlist and the equipment you bring?", "What is your backup if you fall ill?"],
         "contract": ["Hours, overtime rate and sound-limit compliance"]},
        {"category": "invitations", "vendor": "Printer / e-invite designer",
         "ask": ["What is the turnaround and the proofing process?"],
         "contract": ["Final proof sign-off before printing"]},
        {"category": "transport", "vendor": "Transport / guest accommodation",
         "ask": ["Is there a group rate, and what is the cancellation window?"],
         "contract": ["Pick-up schedule and vehicle count"]},
    ],
    "birthday": [
        {"category": "venue", "vendor": "Party venue / hall", "skip_venue": ("home",),
         "ask": ["What is the capacity and what time must we vacate?", "Is outside food and a cake allowed?"],
         "contract": ["Deposit, cancellation terms and any cleaning fee"]},
        {"category": "catering", "vendor": "Caterer / restaurant",
         "ask": ["What is the per-plate price and the minimum headcount?", "Do you serve kids' portions and snacks?"],
         "contract": ["Final headcount deadline", "Menu and serving time"]},
        {"category": "cake", "vendor": "Baker (cake)",
         "ask": ["Is an eggless / sugar-free option available?", "Who handles delivery and what is the time slot?"],
         "contract": ["Design, size, flavour and delivery time confirmed in writing"]},
        {"category": "decor", "vendor": "Decorator / balloon artist",
         "ask": ["Can you work within my theme and budget?", "How long does setup take?"],
         "contract": ["Itemised quote and setup time"]},
        {"category": "entertainment", "vendor": "Entertainer / DJ / game host",
         "ask": ["What age group do you suit, and how long is the act?"],
         "contract": ["Duration, travel charges and cancellation terms"]},
    ],
    "community": [
        {"category": "venue", "vendor": "Venue / ground owner", "skip_venue": ("home",),
         "ask": ["What is the capacity, and are parking and washrooms available?", "Are there noise or closing-time limits?"],
         "contract": ["Permission letter, fee and damage-deposit terms"]},
        {"category": "permits_security", "vendor": "Permissions, security and first aid",
         "ask": ["Which approvals are needed (local body, society, police, fire)?", "How many security and first-aid volunteers do we need?"],
         "contract": ["Written approvals kept on site", "Emergency contact list"]},
        {"category": "sound_av", "vendor": "Sound, stage and lighting",
         "ask": ["What equipment fits the venue size and number of performers?", "Do you provide a technician on site?"],
         "contract": ["Equipment list, setup time and power requirements"]},
        {"category": "catering", "vendor": "Caterer / food stalls",
         "ask": ["Can you serve my expected crowd within an hour?", "Which licences do you hold (food safety)?"],
         "contract": ["Quantity, price per plate and serving window"]},
        {"category": "publicity", "vendor": "Printer / social media volunteer",
         "ask": ["What is the print turnaround for posters and banners?"],
         "contract": ["Quantities and delivery date"]},
        {"category": "entertainment", "vendor": "Performers / speakers",
         "ask": ["What is the time slot, fee (if any) and technical needs?"],
         "contract": ["Confirmed schedule and backup performer"]},
    ],
}

# Context-driven vendors, appended to every event type when the condition applies.
EXTRA_VENDORS = [
    {"category": "tent", "vendor": "Tent / shamiana and weather cover", "only_venue": ("outdoor",),
     "ask": ["Is the tent rated for wind and rain, and who is on call on the day?"],
     "contract": ["Setup and teardown times", "Weather-damage responsibility"]},
    {"category": "power", "vendor": "Generator / power backup", "only_venue": ("outdoor",),
     "ask": ["What load does your generator carry and is a technician included?"],
     "contract": ["Fuel, noise limits and refuelling plan"]},
    {"category": "accessibility", "vendor": "Accessible seating and ramps", "only_attendee": "seniors",
     "ask": ["Are there step-free entry, reserved seating near exits and a quiet rest area?"],
     "contract": ["Reserved front-row seating and accessible washroom access"]},
    {"category": "kids_safety", "vendor": "Kids' activity host / safety", "only_attendee": "kids",
     "ask": ["Is the host safety-trained, and what is the adult-to-child ratio?"],
     "contract": ["Activity list, duration and first-aid cover"]},
]

IDEAS = {
    "wedding": {
        "traditional": ["Marigold and mango-leaf mandap with brass lamps and a traditional welcome (aarti) for guests",
                        "Live shehnai or nadaswaram at the entrance, with a classical-fusion band for the evening",
                        "Regional banana-leaf feast with a handwritten menu card at every table"],
        "modern": ["Pastel floral arches with a minimalist stage and warm fairy-light canopy",
                   "A live illustrator sketching the couple and guests as keepsakes",
                   "Signature mocktail bar named after the couple's inside jokes"],
        "minimal": ["Intimate ceremony with seasonal flowers in clay pots and candlelit tables",
                    "Single-colour palette with printed vows as favours",
                    "Brunch-style reception to cut venue and catering cost"],
        "fun": ["Photo-booth wall with props and an instant-print station",
                "Dance-floor games and a surprise flash-mob from friends",
                "Guest 'advice jar' cards read out at the reception"],
    },
    "birthday": {
        "traditional": ["Rangoli welcome at the door with a home-style thali and sweets",
                        "Family blessing ritual before cake-cutting",
                        "Classic games: antakshari, musical chairs and pass-the-parcel"],
        "modern": ["Colour-block balloon garland with a dessert table and neon sign",
                   "Polaroid memory wall where guests leave a note",
                   "Build-your-own pizza or taco station"],
        "minimal": ["Small dinner with a handwritten menu and a single statement cake",
                    "Picnic-style gathering with blankets and potted plants",
                    "Memory jar of wishes from each guest"],
        "fun": ["Treasure hunt with riddles leading to the cake",
                "Karaoke battle with homemade trophies",
                "Costume or themed dress-up with a prize for the best one"],
    },
    "community": {
        "traditional": ["Cultural evening with local folk performances and a shared meal",
                        "Rangoli and craft competition for neighbours",
                        "Lamp-lighting ceremony to open the event"],
        "modern": ["Pop-up market for local makers and home bakers",
                   "Open-mic stage with a simple sign-up QR code",
                   "Live-streamed highlights for members who cannot attend"],
        "minimal": ["Potluck gathering with a simple programme and one keynote",
                    "Neighbourhood clean-up followed by tea and snacks",
                    "Storytelling circle for elders and children"],
        "fun": ["Inter-lane sports day with relay races and tug-of-war",
                "Quiz night with team names and small prizes",
                "Food-stall challenge where families vote for their favourite dish"],
    },
}

INTEREST_IDEAS = {
    "music": "Curate a live playlist moment: a surprise live singer or a guest-request song wall",
    "food": "Add a regional street-food counter or a chef's special live station",
    "nature": "Use potted plants and seasonal flowers as decor and give saplings as favours",
    "sports": "Set up a friendly tournament corner (carrom, cricket, badminton) with small prizes",
    "art": "Invite a live painter or set up a collaborative canvas guests can add to",
    "travel": "Decorate tables as places the guest of honour has visited, with passport-style programmes",
    "movies": "Use a favourite film as the theme, with a short slideshow or a movie-poster backdrop",
    "books": "Create a book swap or reading nook and give bookmarks as favours",
    "tech": "Run a QR-code photo wall or a digital guestbook guests can scan",
    "dance": "Plan a choreographed family dance and an open dance-floor hour",
}

CONTEXT_IDEAS = {
    "kids": "Set up a supervised kids' corner with colouring, craft and a quiet area",
    "seniors": "Reserve comfortable seating near the stage and exits for elders, with a helper assigned",
    "dietary": "Label every dish with dietary tags so guests can self-serve confidently",
    "outdoor": "Use lanterns and warm string lights for evening ambience, plus a shaded seating area",
}
