import numpy as np
import pandas as pd
import os, re, time, glob, requests, json, pickle

from .football_utilities import *

class FFLeague:
    def __init__(self, name='NFL', league_id=None, path=os.getcwd()):
        self.name = name
        self.path = path
        if league_id is not None:
            self.league_id = str(league_id)
        else:
            self.league_id = None
        owner_path = os.path.join(self.path, 'owners.txt')
        if os.path.exists(owner_path):
            with open(os.path.join(path, 'owners.txt')) as f:
                self.owners = [i.strip() for i in f.readlines()]
        else:
            self.owners = None

        self.team_dir = os.path.join(self.path, 'Teams')
        self.proj_dir = os.path.join(self.path, 'Projections', 'ESPN')
        self.score_dir = os.path.join(self.path, 'Scores', 'ESPN')

        for dirname in [self.team_dir, self.proj_dir, self.score_dir]:
            if not os.path.exists(dirname):
                os.makedirs(dirname)

    def __repr__(self):
        return '<%s - ESPN League: %s>' %(self.name, self.league_id)

    def get_rosters(self, week, write=True):
        if not self.league_id:
            raise RuntimeError("Cannot get rosters without ESPN league ID.")
        url = 'http://games.espn.com/ffl/leaguerosters?leagueId=%s' %self.league_id
        d = pd.read_html(url, attrs={'class': 'playerTableTable tableBody'})
        if self.owners:
            if len(self.owners) != len(d):
                raise RuntimeError("Number of owners provided doesn't match number of rosters scraped.")
        else:
            self.owners = ['Owner%d' %i for i in range(len(d))]
        rosters = pd.DataFrame()
        teams = []
        r = re.compile('(.*?) \((\d)-(\d)\)')

        for n, roster in enumerate(d):
            m = r.match(roster.iloc[0,0])
            roster.drop(range(2), inplace=True)
            roster.columns = ['Slot', 'Player', 'Acq']
            roster.Player = roster.Player.astype('unicode')
            roster.dropna(0, inplace=True)
            info = roster.Player.apply(split_espn_plr)
            roster.drop('Player', axis=1, inplace=True)
            roster.insert(0, 'Player', [i[0] for i in info])
            roster.insert(1, 'Team', [i[1] for i in info])
            roster.insert(1, 'Pos', [i[2] for i in info])
            roster.insert(3, 'Owner', self.owners[n])
            rosters = pd.concat([rosters, roster])
            teams.append({'Owner': self.owners[n], 'Team': m.group(1), 'W': int(m.group(2)), 'L': int(m.group(3))})

        rosters.reset_index(drop=True, inplace=True)
        teams = pd.DataFrame.from_records(teams)
        teams = teams.reindex_axis(['Owner', 'Team', 'W', 'L'], axis=1)

        if write:
            rosters.to_csv(os.path.join(self.team_dir, 'Rosters_Wk%d_%s.csv' %(week, time.strftime('%Y%m%d%H%M'))), index=False)
            teams.to_csv(os.path.join(self.team_dir, 'TeamInfo_Wk%d_%s.csv' %(week, time.strftime('%Y%m%d%H%M'))), index=False)

        self.rosters = rosters
        self.team_info = teams
        return rosters, teams

    def get_proj(self, week, write=True):
        url_str = 'http://games.espn.com/ffl/tools/projections?&scoringPeriodId=%d&seasonId=2016&slotCategoryId=%d&startIndex=%d'

        columns = ['Player', 'OwnCode', 'Action', 'Opp', 'GameTime', 'Cmp_Att',
                   'PsYds', 'PsTD', 'Int', 'RsAtt', 'RsYds', 'RsTD', 'Rec',
                   'RcYds', 'RcTD', 'FFPts']
        k_columns = ['Player', 'OwnCode', 'Action', 'Opp', 'GameTime', '1_39',
                     '40_49', '50plus', 'KTot', 'XP', 'FFPts']

        all_columns = ['Player', 'OwnCode', 'Action', 'Team', 'Pos', 'Opp', 'GameTime',
                       'Cmp_Att', 'PsYds', 'PsTD', 'Int', 'RsAtt', 'RsYds',
                       'RsTD', 'Rec', 'RcYds', 'RcTD', '1_39', '40_49',
                       '50plus', 'KTot', 'XP', 'FFPts']

        if self.league_id:
            url_str += '&leagueId=%s' %self.league_id
        else:
            columns = [i for i in columns if i not in ['OwnCode', 'Action']]
            k_columns = [i for i in k_columns if i not in ['OwnCode', 'Action']]
            all_columns = [i for i in all_columns if i not in ['OwnCode', 'Action']]

        proj = pd.DataFrame()

        for pos_id, pos in zip([0, 2, 4, 6, 16, 17],
                               ['QB', 'RB', 'WR', 'TE', 'DST', 'K']):
            print "Scraping projections for %ss" %pos
            idx = 0
            while True:
                url = url_str %(week, pos_id, idx)
                r = requests.get(url)
                d = pd.read_html(r.content, attrs={'id': 'playertable_0'})
                assert len(d) == 1
                d = d[0]
                if d.shape[0] == 1:
                    break
                d.drop(range(2), inplace=True)
                if pos == 'K':
                    d.columns = k_columns
                else:
                    d.columns = columns
                d.insert(2, 'Pos', pos)
                proj = pd.concat([proj, d])
                # ESPN shows 40 players per page
                idx += 40

        info = proj.Player.apply(split_espn_plr)
        proj['Player'] = [i[0] for i in info]
        proj.insert(2, 'Team', [i[1] for i in info])
        if 'Action' in proj:
            proj.drop('Action', axis=1, inplace=True)
        proj = proj.replace('--', np.nan)
        proj = proj.apply(pd.to_numeric, errors='ignore')

        proj.reset_index(drop=True, inplace=True)
        proj = proj.reindex_axis(all_columns, 1)

        if write:
            proj.to_csv(os.path.join(self.proj_dir, 'Projections_2016Wk%d_%s.csv' %(week, time.strftime('%Y%m%d'))), index=False)

        return proj

    def get_scores(self, week, write=True):
        url_str = 'http://games.espn.com/ffl/leaders?&scoringPeriodId=%d&seasonId=2016&slotCategoryId=%d&startIndex=%d'

        columns = ['Player', 'OwnCode', 'Action', 'Opp', 'WLScore', 'Cmp_Att',
                   'PsYds', 'PsTD', 'Int', 'RsAtt', 'RsYds', 'RsTD', 'Rec',
                   'RcYds', 'RcTD', 'Tgt', '2PC', 'FumL', 'MiscTD', 'FFPts']

        if self.league_id:
            url_str += '&leagueId=%s' %self.league_id
        else:
            columns = [i for i in columns if i not in ['OwnCode', 'Action']]

        score = pd.DataFrame()

        for pos_id, pos in zip([0, 2, 4, 6, 16, 17],
                               ['QB', 'RB', 'WR', 'TE', 'DST', 'K']):
            print "Scraping scores for %ss" %pos
            idx = 0
            while True:
                url = url_str %(week, pos_id, idx)
                r = requests.get(url)
                d = pd.read_html(r.content, attrs={'id': 'playertable_0'})
                assert len(d) == 1
                d = d[0]
                if d.shape[0] == 1:
                    break
                d.drop(range(2), inplace=True)
                # columns to drop depends on whether league columns are there
                if self.league_id:
                    d.drop([1,4,7,12,16,21,25], axis=1, inplace=True)
                else:
                    d.drop([1,4,9,13,18,22], axis=1, inplace=True)
                d.columns = columns
                d.insert(2, 'Pos', pos)
                score = pd.concat([score, d])
                idx += 50 #scoring leaders show 50 per page, vs 40 for projections

        info = score.Player.apply(split_espn_plr)
        score['Player'] = [i[0] for i in info]
        score.insert(2, 'Team', [i[1] for i in info])
        if 'Action' in score:
            score.drop('Action', axis=1, inplace=True)
        score = score.replace('--', np.nan)
        score = score.apply(pd.to_numeric, errors='ignore')

        score.reset_index(drop=True, inplace=True)

        if write:
            score.to_csv(os.path.join(self.score_dir, 'Scores_2016Wk%d_%s.csv' %(week, time.strftime('%Y%m%d%H%M'))), index=False)

        return score

    def merge_proj_scores(self, week, all_players=True, return_scoretime=False):

        proj_fname = sorted(glob.glob(os.path.join(self.proj_dir, 'Projections*Wk%d*.csv' %week)))[-1]
        score_fname = sorted(glob.glob(os.path.join(self.score_dir, 'Scores*Wk%d*.csv' %week)))[-1]
        proj = pd.read_csv(proj_fname)
        score = pd.read_csv(score_fname)
        pp = pd.merge(proj, score, on=['Player', 'Team', 'Pos'], how='outer', suffixes=['_proj', '_real'])

        if self.league_id:
            roster_fname = sorted(glob.glob(os.path.join(self.team_dir, 'Rosters_Wk%d*.csv' %week)))[-1]
            rosters = pd.read_csv(roster_fname)
            if all_players:
                how = 'outer'
            else:
                how = 'inner'
            pp = pd.merge(rosters, pp, on=['Player', 'Team', 'Pos'], how=how)
            if not all_players:
                assert pp.shape[0] == rosters.shape[0]

        score_time = os.path.basename(score_fname).split('_')[-1].replace('.csv', '')
        score_time = time.strptime(score_time, '%Y%m%d%H%M')
        score_time = time.strftime('%A %m/%d at %I:%M %p', score_time)

        if return_scoretime:
            return pp, score_time
        else:
            return pp

    def output_vis_json(self, week):
        if not self.league_id:
            raise RuntimeError("Cannot output team data without ESPN league ID.")
        pp, score_time = self.merge_proj_scores(week, all_players=False, return_scoretime=True)
        json_out = [{'scoreTime': score_time}]
        order = ['QB', 'RB', 'WR', 'TE', 'K', 'D/ST', 'FLEX']
        pl = pp.groupby(['Owner', 'Slot']).agg({'FFPts_proj': np.sum,
                                                'FFPts_real': np.sum,
                                                'Player': lambda x: ' & '.join(x)})
        pl.reset_index(inplace=True)
        pl.fillna("null", inplace=True)
        gb = pl.groupby('Owner')
        for owner in gb.groups:
            out, data_out = {}, []
            out['owner'] = owner
            d = gb.get_group(owner).set_index('Slot')
            for pos in order:
                data_out.append({'Slot': pos,
                                 'proj': d.ix[pos]['FFPts_proj'],
                                 'pts': d.ix[pos]['FFPts_real'],
                                 'player': d.ix[pos]['Player']})
                out['data'] = data_out
            json_out.append(out)

        vis_dir = os.path.join(self.path, 'Visualizations')
        if not os.path.exists(vis_dir):
            os.mkdir(vis_dir)

        with open(os.path.join(vis_dir, 'wk%d.json' %week), 'w') as f:
            json.dump(json_out, f)
