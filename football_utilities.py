import re

short_dict = {'DEN': ['Denver', 'Broncos'],
             'MIA': ['Miami', 'Dolphins'],
             'GNB': ['Green Bay', 'Packers', 'GB'],
             'JAC': ['Jacksonville', 'Jaguars', 'JAX'],
             'NOR': ['New Orleans', 'Saints', 'NO'],
             'NYJ': ['Jets'],
             'BAL': ['Baltimore', 'Ravens'],
             'NYG': ['Giants'],
             'CIN': ['Cincinnati', 'Bengals'],
             'OAK': ['Oakland', 'Raiders'],
             'NWE': ['New England', 'Patriots', 'NE'],
             'PHI': ['Philadelphia', 'Eagles'],
             'CAR': ['Carolina', 'Panthers'],
             'SFO': ['San Francisco', '49ers', 'SF'],
             'IND': ['Indianapolis', 'Colts'],
             'ATL': ['Atlanta', 'Falcons'],
             'LAR': ['Los Angeles', 'Rams', 'St. Louis', 'Saint Louis', 'STL', 'LA'],
             'TAM': ['Tampa Bay', 'Tampa', 'Buccaneers', 'Bucs', 'TB'],
             'KAN': ['Kansas City', 'Kansas', 'Chiefs', 'KC'],
             'WAS': ['Washington', 'Redskins', 'WSH'],
             'CLE': ['Cleveland', 'Browns'],
             'TEN': ['Tennessee', 'Titans'],
             'DET': ['Detroit', 'Lions'],
             'MIN': ['Minnesota', 'Vikings'],
             'SEA': ['Seattle', 'Seahawks'],
             'PIT': ['Pittsburgh', 'Steelers'],
             'CHI': ['Chicago', 'Bears'],
             'SDG': ['San Diego', 'Chargers', 'SD'],
             'BUF': ['Buffalo', 'Bills'],
             'DAL': ['Dallas', 'Cowboys'],
             'ARI': ['Arizona', 'Cardinals'],
             'HOU': ['Houston', 'Texans'],
             'FA': ['Free Agent', 'Free', 'Agent']}

team_dict = {}

for team, shorts in short_dict.iteritems():
    for name in shorts:
        team_dict[name.upper()] = team

def get_team_abbr(x):
    x = x.upper()
    if x in team_dict.values():
        return x
    else:
        return team_dict[x]

def split_espn_plr(x):
    if ',' in x:
        name, team, pos = re.match('(.*?), (.*?)\xa0(\w*)', x).groups()
    else:
        name, pos = x.split(' ')[0], 'DST'
        team = name
    name = name.replace('*', '')
    team = get_team_abbr(team)
    return name, team, pos

fantasy_slots = ['QB', 'RB', 'WR', 'TE', 'D/ST', 'K', 'FLEX']
