import numpy as np
import pandas as pd
import os, re, time, glob, requests, json, pickle, datetime

from .football_utilities import *


_score_columns = dict(OFF = ['Player', 'Opp', 'WLScore', 'Cmp_Att',
                             'PsYds', 'PsTD', 'Int', 'RsAtt', 'RsYds', 'RsTD', 'Rec',
                             'RcYds', 'RcTD', 'Tgt', '2PC', 'FumL', 'MiscTD', 'FFPts'],
                      K = ['Player', 'Opp', 'GameTime', '1_39',
                           '40_49', '50plus', 'KTot', 'XP', 'FFPts'],
                      DST = ['Player', 'Opp', 'WLScore', 'DefTD', 'Int',
                             'FumR', 'Sack', 'Sfty', 'Blk', 'PtsAlld', 'FFPts'],
                      ALL = ['Player', 'Team', 'Pos', 'Opp', 'WLScore', 'Cmp_Att',
                             'PsYds', 'PsTD', 'Int', 'RsAtt', 'RsYds', 'RsTD', 'Rec',
                             'RcYds', 'RcTD', 'Tgt', '2PC', 'FumL', 'MiscTD',
                             'DefTD', 'FumR', 'Sack', 'Sfty', 'Blk', 'PtsAlld',
                             '1_39', '40_49', '50plus', 'KTot', 'XP', 'FFPts'])

_proj_columns = dict(OFF=['Player', 'Opp', 'GameTime', 'Cmp_Att',
                          'PsYds', 'PsTD', 'Int', 'RsAtt', 'RsYds', 'RsTD', 'Rec',
                          'RcYds', 'RcTD', 'FFPts'],
                     K=['Player', 'Opp', 'GameTime', '1_39',
                        '40_49', '50plus', 'KTot', 'XP', 'FFPts'],
                     DST=['Player', 'Opp', 'GameTime', 'TT',
                          'Sck', 'FumF', 'FumR', 'Int', 'IntTD', 'FumTD', 'FFPts'],
                     ALL = ['Player', 'Team', 'Pos', 'Opp', 'GameTime',
                            'Cmp_Att', 'PsYds', 'PsTD', 'Int', 'RsAtt', 'RsYds',
                            'RsTD', 'Rec', 'RcYds', 'RcTD', '1_39', '40_49',
                            '50plus', 'KTot', 'XP', 'TT', 'Sck', 'FumF', 'FumR',
                            'Int', 'IntTD', 'FumTD','FFPts'])

_drop_cols = dict(OFF=[[1,4,9,13,18,22], [1,2,3,4,7,12,16,21,25]],
                  DST=[[1,4,12], [1,2,3,4,7,15]],
                  K=[[1,4,10], [1,2,3,4,7,13]])

class FFLeague:
    curr_year = datetime.datetime.now().year
    def __init__(self, name='NFL', league_id=None, season=curr_year, path=os.getcwd()):
        self.name = name
        self.season = season
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
        self.vis_dir = os.path.join(self.path, 'Visualizations')

        for dirname in [self.team_dir, self.proj_dir, self.score_dir, self.vis_dir]:
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
        r = re.compile('(.*?) \((\d+)-(\d+)\)')

        for n, roster in enumerate(d):
            m = r.match(roster.iloc[0,0])
            roster.drop(range(2), inplace=True)
            roster.columns = ['Slot', 'Player', 'Acq']
            roster.Player = roster.Player.astype('unicode')
            roster.dropna(0, inplace=True)
            info = roster.Player.apply(split_espn_plr).apply(pd.Series)
            roster.drop('Player', axis=1, inplace=True)
            roster.insert(0, 'Player', info[0])
            roster.insert(1, 'Team', info[1])
            roster.insert(2, 'Pos', info[2])
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
        url_str = 'http://games.espn.com/ffl/tools/projections?&scoringPeriodId=%d&seasonId=%d&slotCategoryId=%d&startIndex=%d'
        if self.league_id:
            url_str += '&leagueId=%s' %self.league_id

        proj = pd.DataFrame()
        for pos_id, pos in zip([0, 2, 4, 6, 16, 17],
                               ['QB', 'RB', 'WR', 'TE', 'DST', 'K']):
            print "Scraping projections for %ss" %pos
            idx = 0
            while True:
                url = url_str %(week, self.season, pos_id, idx)
                r = requests.get(url)
                d = pd.read_html(r.content, attrs={'id': 'playertable_0'})
                assert len(d) == 1
                d = d[0]
                if d.shape[0] == 1:
                    break
                d.drop(range(2), inplace=True)
                if self.league_id:
                    d.drop([1,2], axis=1, inplace=True)
                if pos == 'DST' or pos == 'K':
                    d.columns = _proj_columns[pos]
                else:
                    d.columns = _proj_columns['OFF']
                d.insert(2, 'Pos', pos)
                proj = pd.concat([proj, d])
                # ESPN shows 40 players per page
                idx += 40

        proj = proj.replace('--', np.nan)
        proj = proj.replace('--/--', np.nan)
        info = proj.Player.apply(split_espn_plr).apply(pd.Series)
        proj['Player'] = info[0]
        proj['Team'] = info[1]
        proj = proj.reindex_axis(_proj_columns['ALL'], axis=1)
        proj = proj.apply(pd.to_numeric, errors='ignore')
        proj.reset_index(drop=True, inplace=True)

        if write:
            proj.to_csv(os.path.join(self.proj_dir, 'Projections_%dWk%d_%s.csv' \
            %(self.season, week, time.strftime('%Y%m%d%H%M'))), index=False)

        return proj


    def _drop_useless_cols(self, df, pos):
        idx = self.league_id is not None
        if pos == 'DST' or pos == 'K':
            df.drop(_drop_cols[pos][idx], axis=1, inplace=True)
            df.columns = _score_columns[pos]
        else:
            df.drop(_drop_cols['OFF'][idx], axis=1, inplace=True)
            df.columns = _score_columns['OFF']
        return df


    def get_scores(self, week, write=True):
        url_str = 'http://games.espn.com/ffl/leaders?&scoringPeriodId=%d&seasonId=%d&slotCategoryId=%d&startIndex=%d'
        if self.league_id:
            url_str += '&leagueId=%s' %self.league_id

        score = pd.DataFrame()
        for pos_id, pos in zip([0, 2, 4, 6, 16, 17],
                               ['QB', 'RB', 'WR', 'TE', 'DST', 'K']):
            print "Scraping scores for %ss" %pos
            idx = 0
            while True:
                url = url_str %(week, self.season, pos_id, idx)
                try:
                    r = requests.get(url)
                except:
                    raise RuntimeError("There was an error scraping data from ESPN.")
                d = pd.read_html(r.content, attrs={'id': 'playertable_0'})
                assert len(d) == 1
                d = d[0]
                if d.shape[0] == 1:
                    break
                d.drop(range(2), inplace=True)
                d = self._drop_useless_cols(d, pos)
                d.insert(2, 'Pos', pos)
                score = pd.concat([score, d])
                idx += 50 #scoring leaders show 50 per page, vs 40 for projections

        score = score.replace('--', np.nan)
        score = score.replace('--/--', np.nan)
        info = score.Player.apply(split_espn_plr).apply(pd.Series)
        score['Player'] = info[0]
        score['Team'] = info[1]
        score = score.reindex_axis(_score_columns['ALL'], axis=1)
        score = score.apply(pd.to_numeric, errors='ignore')
        score.reset_index(drop=True, inplace=True)

        if write:
            score.to_csv(os.path.join(self.score_dir, 'Scores_%dWk%d_%s.csv' \
            %(self.season, week, time.strftime('%Y%m%d%H%M'))), index=False)

        return score

    def merge_proj_scores(self, week, all_players=True, prev_weeks=False, return_times=False):

        if prev_weeks:
            weeks = np.arange(1, week+1)
        else:
            weeks = [week]

        out = pd.DataFrame()
        for week in weeks:
            proj_fnames = sorted(glob.glob(os.path.join(self.proj_dir, 'Projections*Wk%d*.csv' %week)))
            if not proj_fnames:
                raise RuntimeError("No projection file found for week %d. " %week + \
                                    "Please scrape it using `get_proj()`.")
            else:
                proj_fname = proj_fnames[-1]
            score_fnames = sorted(glob.glob(os.path.join(self.score_dir, 'Scores*Wk%d*.csv' %week)))
            if not score_fnames:
                raise RuntimeError("No score file found for week %d. " %week + \
                                    "Please scrape it using `get_scores()`.")
            else:
                score_fname = score_fnames[-1]
            proj = pd.read_csv(proj_fname)
            score = pd.read_csv(score_fname)
            pp = pd.merge(proj, score, on=['Player', 'Team', 'Pos'], how='outer', suffixes=['_proj', '_real'])
            roster_fname = None

            if self.league_id:
                roster_fnames = sorted(glob.glob(os.path.join(self.team_dir, 'Rosters_Wk%d*.csv' %week)))
                if not roster_fnames:
                    raise RuntimeError("No roster file found for week %d. " %week + \
                                        "Please scrape it using `get_past_rosters()` " + \
                                        "or `get_rosters()` if it is the current week.")
                else:
                    roster_fname = roster_fnames[-1]
                rosters = pd.read_csv(roster_fname)
                how = 'outer' if all_players else 'inner'
                pp = pd.merge(rosters, pp, on=['Player', 'Team', 'Pos'], how=how)
                if not all_players:
                    assert pp.shape[0] == rosters.shape[0]

            pp.insert(1, 'Week', week)
            out = pd.concat([out, pp])

        pp = out

        if return_times:
            times = {}
            for label, fname in zip(['projTime', 'scoreTime', 'rosterTime'], [proj_fname, score_fname, roster_fname]):
                if fname:
                    time_str = os.path.basename(fname).split('_')[-1].replace('.csv', '')
                    time_str = time.strptime(time_str, '%Y%m%d%H%M')
                    time_str = time.strftime('%A %m/%d at %I:%M %p', time_str)
                    times[label] = time_str

            return pp, times

        else:
            return pp


    def output_week_vis_json(self, week):
        if not self.league_id:
            raise RuntimeError("Cannot output team data without ESPN league ID.")
        pp, times = self.merge_proj_scores(week, all_players=False, return_times=True)
        json_out = [times]
        order = ['QB', 'RB', 'WR', 'TE', 'K', 'D/ST', 'FLEX']
        pl = pp.groupby(['Owner', 'Slot']).agg({'FFPts_proj': np.sum,
                                                'FFPts_real': np.sum,
                                                'Player': lambda x: ' & '.join(x)})
        pl.reset_index(inplace=True)
        pl.FFPts_proj.fillna(0, inplace=True)
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

        with open(os.path.join(self.vis_dir, 'wk%d.json' %week), 'w') as f:
            json.dump(json_out, f)

    def output_team_vs_average_json(self, max_week):
        if not self.league_id:
            raise RuntimeError("Cannot output team data without ESPN league ID.")

        json_out = []
        data = pd.DataFrame()
        for week in range(1, max_week+1):
            pp = self.merge_proj_scores(week, all_players=False)
            data = pd.concat([data, pp])

        # get team info (with WL) from the first file scraped after the week switches over
        info_fname = sorted(glob.glob(os.path.join(self.path, 'Teams', 'TeamInfo*Wk%d*.csv' %(max_week+1))))[0]
        info = pd.read_csv(info_fname).set_index('Owner')
        info['record'] = info.apply(lambda r: '%d-%d' %(r['W'], r['L']), 1)

        team_aves = data.groupby(['Owner', 'Slot']).sum()['FFPts_real']/float(max_week)
        team_aves = team_aves.reset_index()
        lg_aves = data.groupby(['Slot']).sum()['FFPts_real']/(float(max_week)*len(self.owners))
        team_aves['Pct'] = team_aves.apply(lambda r: (r['FFPts_real']-lg_aves[r['Slot']])/lg_aves[r['Slot']], 1)
        order = ['QB', 'RB', 'WR', 'TE', 'K', 'D/ST', 'FLEX']
        gb = team_aves.groupby('Owner')

        for owner, d in gb:
            d = d.set_index('Slot')
            out = {'Owner': owner, 'Record': info.ix[owner, 'record'], 'data': []}
            for pos in order:
                out['data'].append({'Slot': pos,
                                    'FFPts': d.ix[pos]['FFPts_real'],
                                    'Pct': d.ix[pos]['Pct']})
            json_out.append(out)

        with open(os.path.join(self.vis_dir, 'teams_vs_average.json'), 'w') as f:
            json.dump(json_out, f)


    def get_past_rosters(self, week, write=True):
        url_str = 'http://games.espn.com/ffl/boxscorequick?leagueId=%s&teamId=%d&scoringPeriodId=%d&seasonId=%d&view=scoringperiod&version=quick'
        rosters = []
        for i, owner in enumerate(self.owners):
            url = url_str %(self.league_id, i + 1, week, self.season)
            d = pd.read_html(url, attrs={'id': 'playertable_0'})
            info = d[0].drop(range(3)).dropna(subset=[1])
            slots = info[0]
            info = info[1].apply(split_espn_plr).apply(pd.Series)
            info.columns = ['Player', 'Team', 'Pos']
            info.insert(0, 'Slot', slots)
            info['Owner'] = owner
            rosters.append(info)
        rosters = pd.concat(rosters)

        if write:
            rosters.to_csv(os.path.join(self.team_dir, 'Rosters_Wk%d.csv' %week), index=False)

        return rosters
