"""A portable welcome surface, with an honest text fallback for terminal hosts."""
from .store import PACKAGE

CHOICES = [
    {'id': 'interview', 'label': '1. Curated interview',
     'description': 'A few focused questions at a time to shape your profile, voice, and direction.'},
    {'id': 'files', 'label': '2. Mega file dump',
     'description': 'Bring your source files. I will organize them, propose a profile, and ask about the gaps.'}
]

BANNER = '''
+------------------------------------------------------------------+
|                                                                  |
|                        CONTENTMAXXING                            |
|                      YOUR CREATOR ENGINE                         |
|                                                                  |
|                  CAPTURE  >  CREATE  >  COMPOUND                   |
|                                                                  |
|   [1] CURATED INTERVIEW        [2] MEGA FILE DUMP                   |
|       Find your direction.        Start with your real work.       |
|                                                                  |
+------------------------------------------------------------------+
'''.strip()


def welcome():
    return {'title': 'CONTENTMAXXING', 'tagline': 'Capture → Create → Compound',
            'choices': CHOICES, 'banner': BANNER, 'image': str(PACKAGE / 'assets/welcome.png'),
            'message': 'How would you like to start? You can combine both paths and resume later.'}
