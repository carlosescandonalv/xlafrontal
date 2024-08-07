import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import numpy as np
from mplsoccer.pitch import Pitch, VerticalPitch
from mplsoccer import lines
from scipy.ndimage import gaussian_filter
import datetime
from mplsoccer import FontManager
import matplotlib.font_manager
from IPython.core.display import HTML
import matplotlib as mpl
from PIL import Image
from mplsoccer import VerticalPitch, add_image, FontManager
import os
import plotly.graph_objects as go
import plotly.express as px
import json 
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap


def create_connection():
    conn = psycopg2.connect(
            user = "postgres.ztcwzgcdqaecducpznat",
            password= 'PTNRNRWooVK0bmvr',
            host="aws-0-eu-west-2.pooler.supabase.com",
            port="6543",
            database ="postgres"
        )
    return conn

def season_list():
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute("""
       SELECT season_id FROM season
        """)
    records = cursor.fetchall()
    seasons = [season[0] for season in records]
    return seasons

def team_list(season):    # Create a list with all the teams avilable
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT participants FROM season
        WHERE season_id = '{season}'
        """)
    records = cursor.fetchall()
    teamslist = json.loads(records[0][0])
    if "Atletico Madrid" in teamslist:
        teamslist[teamslist.index("Atletico Madrid")] = "Atletico"
    return teamslist

def table_extraction(season):    # Classification Dataframe extraction (W,D,L, Points)
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT * FROM matches WHERE season = '{season}'
        """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    team_stats = {}
    def initialize_team(team_name):
        return {
            'matches_won': 0,
            'matches_drawn': 0,
            'matches_lost': 0,
            'goals_scored': 0,
            'goals_received': 0,
            'clean_sheets':0
        }
    # Update the team statistics based on match outcomes
    for index, row in df.iterrows():
        home_team = row['home']
        away_team = row['away']
        goals_h = row['goals_h']
        goals_a = row['goals_a']
        
        if home_team not in team_stats:
            team_stats[home_team] = initialize_team(home_team)
        if away_team not in team_stats:
            team_stats[away_team] = initialize_team(away_team)
        
        team_stats[home_team]['goals_scored'] += goals_h
        team_stats[home_team]['goals_received'] += goals_a
        team_stats[away_team]['goals_scored'] += goals_a
        team_stats[away_team]['goals_received'] += goals_h
        if goals_h == 0:
            team_stats[away_team]['clean_sheets']+=1
        if goals_a == 0:
            team_stats[home_team]['clean_sheets']+=1

        if goals_h > goals_a:
            team_stats[home_team]['matches_won'] += 1
            team_stats[away_team]['matches_lost'] += 1
        elif goals_h < goals_a:
            team_stats[away_team]['matches_won'] += 1
            team_stats[home_team]['matches_lost'] += 1
        else:
            team_stats[home_team]['matches_drawn'] += 1
            team_stats[away_team]['matches_drawn'] += 1

    # Convert the team_stats dictionary to a DataFrame
    team_stats_df = pd.DataFrame.from_dict(team_stats, orient='index')

    team_stats_df['points'] = team_stats_df['matches_won']*3+team_stats_df['matches_drawn']
    team_stats_df = team_stats_df.sort_values(by='points', ascending=True)
    team_stats_df = team_stats_df.reset_index().rename(columns={'index': 'team'})

    return team_stats_df

def table_plot(df):
    fig = px.bar(df, x='team', y='points', title='Points of Each Team', 
                labels={'team': 'Teams', 'points': 'Points'}, 
                color='points', 
                color_continuous_scale='Blues')

    fig.update_layout(xaxis_tickangle=-45)
    return fig
 
def color_rows(row):    # Color the rows of the team classification table
    if row.name < 5:
        return ['background-color: #9CFC97']*len(row) 
    elif row.name < 7:
        return ['background-color: #5BC0EB']*len(row)
    elif row.name >17:
        return ['background-color: #D37773']*len(row)

def get_shot_form(qualifiers):
    for item in qualifiers:
        if 'type' in item and 'displayName' in item['type']:
            display_name = item['type']['displayName']
            if display_name in ['Head', 'RightFoot', 'LeftFoot','OtherBodyPart']:
                return display_name
    return None

def goalscorer_table(season):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT
            me.*,
            p.name
       FROM
            match_event me
       JOIN
            players p ON me.player_id = p.player_id
       JOIN    
            matches m ON me.match_id = m.match_id
       WHERE
            me.is_shot = True AND m.season = '{season}'
        """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    df['shot_form'] = df['qualifiers'].apply(get_shot_form)
    goals_df = df.loc[df['type']=='Goal']
    total_shots = df.groupby(['player_id', 'name']).size().reset_index(name='total_shots')
    goals = df[df['type']=='Goal'].groupby(['player_id']).size().reset_index(name='goals')
    left_goals=  goals_df[goals_df['shot_form'] == 'LeftFoot'].groupby(['player_id']).size().reset_index(name='LeftFoot_goals')
    right_goals=  goals_df[goals_df['shot_form'] == 'RightFoot'].groupby(['player_id']).size().reset_index(name='RightFoot_goals')
    head_goals=  goals_df[goals_df['shot_form'] == 'Head'].groupby(['player_id']).size().reset_index(name='Header_goals')
    other_goals=  goals_df[goals_df['shot_form'] == 'OtherBodyPart'].groupby(['player_id']).size().reset_index(name='OtherBodyPart_goals')
    merged_counts = pd.merge(total_shots, goals, on='player_id', how='left').merge(left_goals,on='player_id',how='left').merge(right_goals,on='player_id',how='left').merge(head_goals,on='player_id',how='left').merge(other_goals,on='player_id',how='left')
    merged_counts.fillna(0, inplace=True)
    top_10_players = merged_counts.sort_values(by='total_shots', ascending=False).head(50)
    top_10_players_sorted = top_10_players.sort_values(by='goals', ascending=False)
    top_10_players_sorted['LeftFoot_goals'] = top_10_players_sorted['LeftFoot_goals'].astype(int)
    top_10_players_sorted['RightFoot_goals'] = top_10_players_sorted['RightFoot_goals'].astype(int)
    top_10_players_sorted['Header_goals'] = top_10_players_sorted['Header_goals'].astype(int)
    top_10_players_sorted['Other'] = top_10_players_sorted['OtherBodyPart_goals'].astype(int)

    top_10_players_sorted = top_10_players_sorted.head(15)
    top_10_players_sorted = top_10_players_sorted.sort_values(by='goals', ascending=True)
    fig, ax = plt.subplots(figsize=(10, 10))

    img_path = 'imgs_app/laligalogo2.png'
    img = plt.imread(img_path)
    imagebox = OffsetImage(img, zoom=0.04)
    ab = AnnotationBbox(imagebox, (1, 1), frameon=False, xycoords='axes fraction', boxcoords="axes fraction", pad=0)
    ax.add_artist(ab)

    bar_width = 0.7
    bar_left = ax.barh(top_10_players_sorted['name'], top_10_players_sorted['LeftFoot_goals'], bar_width, label='Left Foot Goals',color="#59A0A9")
    bar_right = ax.barh(top_10_players_sorted['name'], top_10_players_sorted['RightFoot_goals'], bar_width, left=top_10_players_sorted['LeftFoot_goals'], label='Right Foot Goals',color="#5B59A9")
    bar_head = ax.barh(top_10_players_sorted['name'], top_10_players_sorted['Header_goals'], bar_width, left=top_10_players_sorted['RightFoot_goals']+top_10_players_sorted['LeftFoot_goals'], label='Header Goals',color="#FFFCEE",alpha=0.75)
    bar_other= ax.barh(top_10_players_sorted['name'], top_10_players_sorted['Other'], bar_width, left=top_10_players_sorted['RightFoot_goals']+top_10_players_sorted['LeftFoot_goals']+top_10_players_sorted['Header_goals'], label='Other Goals',color="orange",alpha=0.75)

    fig.set_facecolor('#290028')
    ax.set_facecolor('#290028')

    ax.set_xlabel('Goals Scored',fontsize=12,color='white')
    ax.legend(fontsize=12,borderpad=0.7)

    for player, goals_left, goals_right, goals_head,goals_other in zip(top_10_players_sorted['name'], top_10_players_sorted['LeftFoot_goals'], top_10_players_sorted['RightFoot_goals'], top_10_players_sorted['Header_goals'],top_10_players_sorted['Other']):
        if goals_left != 0:
            ax.text(goals_left / 2, player, str(goals_left), ha='center', va='center', color='white', fontweight='bold')
        if goals_right != 0:
            ax.text(goals_left + goals_right / 2, player, str(goals_right), ha='center', va='center', color='white', fontweight='bold')
        if goals_head != 0:
            ax.text(goals_left + goals_right + goals_head / 2, player, str(goals_head), ha='center', va='center', color='white', fontweight='bold')
        if goals_other != 0:
            ax.text(goals_left + goals_right + goals_head + goals_other/ 2, player, str(goals_other), ha='center', va='center', color='white', fontweight='bold')

    ax.set_title('Goal Scorers tendencies',fontweight='bold',fontsize=16,color='white',y=0.99)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)

    ax.set_yticklabels(top_10_players_sorted['name'], fontsize=12,color='white')
    ax.set_xticklabels(ax.get_xticks(), fontsize=12, fontweight='bold',color='white')
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: int(x)))

    ax.tick_params(axis='both', which='both', length=0)

    return fig

def penalties_season(season,mode):
    conn = create_connection()
    cursor = conn.cursor()
    if mode == "League General":
        cursor.execute(f"""
        SELECT
                me.*,p.name,m.home,m.away
        FROM
                match_event me
        JOIN
                players p ON me.player_id = p.player_id
        JOIN
                matches m ON me.match_id = m.match_id
        WHERE
                me.is_shot = True AND m.season = '{season}';
            """)
    else: 
        cursor.execute(f"""
        SELECT
                me.*,p.name,m.home,m.away, t.name
        FROM
                match_event me
        JOIN
                players p ON me.player_id = p.player_id
        JOIN
                matches m ON me.match_id = m.match_id
        JOIN    teams t ON me.team_id = t.team_id               
        WHERE
                me.is_shot = True AND t.name = '{mode}' AND m.season = '{season}';
            """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    is_penalty = lambda x: any(qualifier.get('type', {}).get('displayName') == 'Penalty' for qualifier in x)
    df['is_penalty'] = df['qualifiers'].apply(is_penalty)
    penalty_rows = df[df['is_penalty']]
    df = df.loc[df['is_penalty'] == True]
    df['goal_mouth_z'] = (df['goal_mouth_z']*2.4)/39.6
    df['goal_mouth_y'] = ((df['goal_mouth_y'] - 45) / (55 - 45)) * (7.2 - 0) + 0
    # Load the image
    image_path = 'imgs_app/porteria.png'
    image = plt.imread(image_path)

    x_min, x_max, y_min, y_max = 0, 7.5, 0, 2.45
    fig, ax = plt.subplots(figsize=(32,6))

    aspect_ratio = (x_max - x_min) / (y_max - y_min)
    ax.imshow(image, extent=(x_min, x_max, y_min, y_max), aspect=aspect_ratio, alpha=0.8)


    plt.gca().invert_xaxis()
    for index,row in df.iterrows():
        color_shot = 'red'
        alpha_c=0.6
        if row['type'] =='Goal':
            color_shot = '#53FF45'
            alpha_c=0.8
        ax.scatter(row['goal_mouth_y'], row['goal_mouth_z'], marker='o', color=color_shot,s=250, label='Goals',alpha=alpha_c,edgecolor='black')

    ax.set_xlim(10, -3)
    ax.set_ylim(-0.2, 4)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect('equal')

    return fig, df


def penaltis_stats(df):
    goal_width = 7.32
    goal_height = 2.44

    # Create a new column to label each shot based on its width (left, mid, right)
    df['width_zone'] = pd.cut(df['goal_mouth_y'], bins=[0, goal_width/3, 2*goal_width/3, goal_width], labels=['right', 'mid', 'left'])

    # Create a new column to label each shot based on its height (top or bottom)
    df['height_zone'] = pd.cut(df['goal_mouth_z'], bins=[0, goal_height/2, goal_height], labels=['bottom', 'top'])

    # Create a combined shot zone column
    df['shot_zone'] = df.apply(lambda row: f"{row['width_zone']}-{row['height_zone']}" if pd.notnull(row['width_zone']) and pd.notnull(row['height_zone']) else 'Out', axis=1)

    # Print the percentage and number of shots for each area
    shot_counts = df['shot_zone'].value_counts(normalize=True) * 100
    shot_counts = shot_counts.sort_index()
    print("Shot Zones:")
    print(shot_counts)
    print("\nNumber of Shots in Each Zone:")
    print(df['shot_zone'].value_counts())
    shot_counts = df['shot_zone'].value_counts(normalize=True) * 100
    shot_counts = shot_counts.sort_index()
    print("Shot Zones:")
    print(shot_counts)
    print("\nNumber of Shots in Each Zone:")
    print(df['shot_zone'].value_counts())
    # Shot zone count and Success Rate of each zone
    a = df['shot_zone'].value_counts()
    success_rate = df.groupby('shot_zone')['type'].apply(lambda x: (x == 'Goal').sum() / len(x) * 100 if len(x) > 0 else 0)
    
    #shot_counts = a.drop('Out')
    #success_rates = success_rate.drop('Out')
    if 'Out' in a.index:
        shot_counts = a.drop('Out')
    else:
        shot_counts = a

    if 'Out' in success_rate.index:
        success_rates = success_rate.drop('Out')
    else:
        success_rates = success_rate
    success_rates = success_rates.reindex(shot_counts.index)
    zone_mapping = {
        'left-top': (0, 0),
        'mid-top': (0, 1),
        'right-top': (0, 2),
        'left-bottom': (1, 0),
        'mid-bottom': (1, 1),
        'right-bottom': (1, 2)
    }
    shot_matrix = [[0, 0, 0], [0, 0, 0]]
    success_matrix = [[0, 0, 0], [0, 0, 0]]

    for zone in shot_counts.index:
        count = shot_counts[zone]
        rate = success_rates[zone]
        row, col = zone_mapping[zone]
        shot_matrix[row][col] = count
        success_matrix[row][col] = rate

    shot_df = pd.DataFrame(shot_matrix, index=['Top', 'Bottom'], columns=['Left', 'Middle', 'Right'])
    success_df = pd.DataFrame(success_matrix, index=['Top', 'Bottom'], columns=['Left', 'Middle', 'Right'])

    fig, ax = plt.subplots(1, 2, figsize=(14, 6))
    sns.heatmap(shot_df, annot=True, fmt='d', cmap='Blues', cbar=True, ax=ax[0])
    ax[0].set_title('Number of Shots by Zone', fontsize=14)
    ax[0].set_xlabel('')
    ax[0].set_ylabel('')
    ax[0].set_xticklabels(['Left', 'Middle', 'Right'], fontsize=12)
    ax[0].set_yticklabels(['Top', 'Bottom'], fontsize=12, rotation=0)
    sns.heatmap(success_df, annot=True, fmt='.1f', cmap='RdYlGn', cbar=True, ax=ax[1])
    ax[1].set_title('Success Rate by Zone (%)', fontsize=14)
    ax[1].set_xlabel('')
    ax[1].set_ylabel('')
    ax[1].set_xticklabels(['Left', 'Middle', 'Right'], fontsize=12)
    ax[1].set_yticklabels(['Top', 'Bottom'], fontsize=12, rotation=0)
    plt.tight_layout()
    
    return fig


### TEAM overview
def possession_zones(team,season):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT * FROM match_event
        JOIN teams ON match_event.team_id = teams.team_id
        JOIN matches ON match_event.match_id = matches.match_id
        WHERE teams.name = '{team}' AND type = 'BallTouch' AND matches.season ='{season}'
        """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    pitch = VerticalPitch(pitch_type='opta', line_zorder=2,
              pitch_color='white', line_color='black',linewidth=1)

    fig, ax = pitch.draw(figsize=(8, 6))
    fig.set_facecolor('white')
    plt.gca().invert_xaxis()
    bin_statistic = pitch.bin_statistic(df.x, df.y, statistic='count', bins=(10, 4),normalize=True)
    bin_statistic['statistic'] = gaussian_filter(bin_statistic['statistic'], 1)
    pcm = pitch.heatmap(bin_statistic, ax=ax, cmap='Reds', edgecolors='white')
    plt.title(f'Team possession zones',loc='center', fontweight='bold')

    labels = pitch.label_heatmap(bin_statistic, color='black', fontsize=8,
                                ax=ax, ha='center', va='center',
                                str_format='{:.0%}',exclude_zeros=True)
    return fig

def passing_flow(team,season):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT match_event.*, teams.name AS team_name,matches.match_date AS match_date, 
       matches.home AS home_team, matches.away AS away_team, matches.goals_h AS goals_home, matches.goals_a AS goals_away
       FROM match_event
       JOIN teams ON match_event.team_id = teams.team_id
       JOIN matches ON match_event.match_id = matches.match_id
       WHERE teams.name = '{team}' AND type = 'Pass'AND matches.season = '{season}'
        """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    pitch = VerticalPitch(pitch_type='opta', line_zorder=2,
              pitch_color='white', line_color='black',linewidth=1)
    bins = (6, 4)
    fig, ax = pitch.draw(figsize=(8, 6))
    fig.set_facecolor('white')
    plt.gca().invert_xaxis()
    bs_heatmap = pitch.bin_statistic(df.x, df.y, statistic='count', bins=bins)
    hm = pitch.heatmap(bs_heatmap, ax=ax, cmap='Blues')
    fm = pitch.flow(df.x, df.y, df.end_x, df.end_y,
                    color='black', arrow_type='same',
                    arrow_length=5, bins=bins, ax=ax)
    ax_title = ax.set_title(f'{team} pass flow season 23/24',pad=-20,color="black",fontweight='bold')

    return fig


def goals_development(team,season):   # Goals development plot for a spcefic team
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT * from matches
       WHERE matches.home = '{team}' OR matches.away = '{team}'
       AND matches.season = '{season}'      
        """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    
    df['match_date'] = pd.to_datetime(df['match_date'])
    df = df.sort_values('match_date')
    unique_dates = df['match_date'].unique()
    date_to_label = {date: f'J{i+1}' for i, date in enumerate(unique_dates)}
    df['match_label'] = df['match_date'].map(date_to_label)

    for index, row in df.iterrows():
        if row['home'] == team:
            df.at[index, 'goals_scored'] = row['goals_h']
            df.at[index, 'goals_conceded'] = row['goals_a']
        elif row['away'] == team:
            df.at[index, 'goals_scored'] = row['goals_a']
            df.at[index, 'goals_conceded'] = row['goals_h']
    df = df.sort_values('match_date')
    goals_scored = int(df['goals_scored'].sum())
    goals_conceded = int(df['goals_conceded'].sum())
    clean_sheets = int((df['goals_conceded']==0).sum())
    # Create the Plotly line chart
    fig = go.Figure()

    # Add trace for goals scored
    fig.add_trace(go.Scatter(
        x=df['match_label'],
        y=df['goals_scored'],
        mode='lines+markers',
        name='Goals Scored',
        line=dict(color='blue'),
        fill='tozeroy',  # Fill the area below the line to the x-axis
        fillcolor='rgba(0, 0, 255, 0.2)'

    ))

    # Add trace for goals conceded
    fig.add_trace(go.Scatter(
        x=df['match_label'],
        y=df['goals_conceded'],
        mode='lines+markers',
        name='Goals Conceded',
        line=dict(color='red'),
        fill='tozeroy',  # Fill the area below the line to the x-axis
        fillcolor='rgba(255, 0, 0, 0.2)'
    ))

    # Update layout
    fig.update_layout(
        title=f'Goals Scored and Conceded by {team} Each Match',
        xaxis_title='Match Date',
        yaxis_title='Goals',
        hovermode='x unified',
        plot_bgcolor = 'white', 
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5
        )
    )

    return fig,goals_scored,goals_conceded,clean_sheets

def determine_outcome(row, variable_team):
        if row['home_team'] == variable_team:
            if row['goals_home'] > row['goals_away']:
                return 'Win'
            elif row['goals_home'] < row['goals_away']:
                return 'Lose'
            else:
                return 'Draw'
        elif row['away_team'] == variable_team:
            if row['goals_away'] > row['goals_home']:
                return 'Win'
            elif row['goals_away'] < row['goals_home']:
                return 'Lose'
            else:
                return 'Draw'
        else:
            return 'N/A'  #
        
def pass_development(team,season):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT match_event.*, teams.name AS team_name,matches.match_date AS match_date, 
       matches.home AS home_team, matches.away AS away_team, matches.goals_h AS goals_home, matches.goals_a AS goals_away
       FROM match_event
       JOIN teams ON match_event.team_id = teams.team_id
       JOIN matches ON match_event.match_id = matches.match_id
       WHERE teams.name = '{team}' AND type = 'Pass'AND matches.season = '{season}'
        """)
    records = cursor.fetchall()
    
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    df = df[df['outcome'] =='Successful']

    df['match_outcome'] = df.apply(lambda row: determine_outcome(row, team), axis=1)

    df['match_date'] = pd.to_datetime(df['match_date'])
    df['match_result'] = df.apply(lambda row: f"{row['home_team']} ({row['goals_home']}) - ({row['goals_away']}) {row['away_team']}", axis=1)

    passes_df = df.sort_values('match_date')
    unique_dates = passes_df['match_date'].unique()
    date_to_label = {date: f'J{i+1}' for i, date in enumerate(unique_dates)}


    grouped = passes_df.groupby('match_date').agg({'type': 'size', 'match_result': 'first','match_outcome':'first'}).reset_index()
    grouped['label'] = grouped['match_result'].astype(str) + ' - ' + grouped['type'].astype(str) + ' Passes'
    
    # Assign colors based on outcome
    color_map = {'Win': '#8ac926', 'Lose': '#ff595e', 'Draw': '#ffca3a'}
    grouped['color'] = grouped['match_outcome'].map(color_map)

    # Create the Plotly bar chart
    fig = go.Figure(data=[
        go.Bar(
            x=[date_to_label[date] for date in grouped['match_date']],
            y=grouped['type'],
            text=grouped['label'],  # Custom labels
            textposition='none',    # Hide text on bars
            hovertemplate='%{text}<extra></extra>',  # Show text on hover
            marker_color=grouped['color']  # Set bar color based on outcome
        )
    ])

    # Update layout
    fig.update_layout(
        title=f'Number of Passes of {team} per Match Date',
        xaxis_title='Match Date',
        yaxis_title='Number of Passes',
        plot_bgcolor = "white"
    )

    return fig


def get_team_info(team):
  team_data = [
    {'Team': 'Deportivo Alaves', 'Crest': 'Alaves.png', 'Color': '#0761AF', 'Color2':'white'},
    {'Team': 'Almeria', 'Crest': 'Almería.png', 'Color': '#ee1119','Color2':'white'},
    {'Team': 'Athletic Club', 'Crest': 'Athletic.png', 'Color': '#EE2523','Color2':'white'},
    {'Team': 'Atletico', 'Crest': 'atletico.png', 'Color': '#CB3524','Color2':'white'},
    {'Team': 'Barcelona', 'Crest': 'Barcelona.png', 'Color': '#A50044','Color2':'#EDBB00'},
    {'Team': 'Real Betis', 'Crest': 'Betis.png', 'Color': '#0BB363','Color2':'white'},
    {'Team': 'Cadiz', 'Crest': 'Cadiz.png', 'Color': '#ffe500','Color2':'blue'},
    {'Team': 'Celta Vigo', 'Crest': 'Celta.png', 'Color': '#8AC3EE','Color2':'#E5254E'},
    {'Team': 'Getafe', 'Crest': 'Getafe.png', 'Color': '#004fa3', 'Color2':'white'},
    {'Team': 'Girona', 'Crest': 'Girona.png', 'Color': '#cd2534','Color2':'#ffee00'},
    {'Team': 'Granada', 'Crest': 'Granada.png', 'Color': '#A61B2B','Color2':'white'},
    {'Team': 'Las Palmas', 'Crest': 'LasPalmas.png', 'Color': '#ffe400','Color2':'blue'},
    {'Team': 'Mallorca', 'Crest': 'Mallorca.png', 'Color': '#E20613','Color2':'yellow'},
    {'Team': 'Osasuna', 'Crest': 'Osasuna.png', 'Color': '#D91A21','Color2':'#0A346F'},
    {'Team': 'Rayo Vallecano', 'Crest': 'RayoVallecano.png', 'Color': '#ff0000','Color2':'white'},
    {'Team': 'Real Madrid', 'Crest': 'RealMadrid.png', 'Color': 'white','Color2':'blue'},
    {'Team': 'Real Sociedad', 'Crest': 'RealSociedad.png', 'Color': '#0067B1','Color2':'white'},
    {'Team': 'Sevilla', 'Crest': 'Sevilla.png', 'Color': '#F43333','Color2':'white'},
    {'Team': 'Valencia', 'Crest': 'Valencia.png', 'Color': '#D18816','Color2':'black'},
    {'Team': 'Villarreal', 'Crest': 'Villarreal.png', 'Color': '#FFE667','Color2':'#005187'}
    ]
  team_info_a = next((item for item in team_data if item['Team'] == team), None)
  crest_filename_a = team_info_a['Crest']
  teamcrest_path_a = os.path.join('imgs_app/LaLigaCrests', crest_filename_a)
  crest_img = Image.open(teamcrest_path_a)
  crest_img = crest_img.resize((150, 150),Image.ADAPTIVE)

  color1= next((item['Color'] for item in team_data if item['Team'] == team), None)
  color2= next((item['Color2'] for item in team_data if item['Team'] == team), None)
  return crest_img,color1,color2

def get_team_event_xi(team,season):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT match_event.*, matches.season AS season, players.name AS player_name, players.shirt_no AS number,
                   teams.name AS team_name FROM match_event
        JOIN players ON match_event.player_id = players.player_id
        JOIN teams ON match_event.team_id = teams.team_id
        JOIN matches ON match_event.match_id = matches.match_id
        WHERE teams.name = '{team}' AND matches.season = '{season}'
        """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    return df


def get_xi(df):
  match_ids = df['match_id'].unique()
  total_player_minutes = {}
  player_numbers = {}
  for match_id in match_ids:
      match_events = df[df['match_id'] == match_id]
      max_minute = 90
      player_minutes = {}

      for index, row in match_events.iterrows():
          player = row['player_name']
          minute = row['minute']
          event_type = row['type']
          player_number = row['number']

          if player not in player_numbers:
              player_numbers[player] = player_number
          if event_type == 'SubstitutionOn':
              if player not in player_minutes:
                  player_minutes[player] = max_minute - minute
              else:
                  player_minutes[player] += max_minute - minute
          elif event_type == 'SubstitutionOff':
              if player not in player_minutes:
                  player_minutes[player] = minute
              else:
                  player_minutes[player] += minute

      all_players = set(match_events['player_name'].unique())
      for player in all_players:
          if player not in player_minutes:
              player_minutes[player] = max_minute

      for player, minutes in player_minutes.items():
          if player in total_player_minutes:
              total_player_minutes[player] += minutes
          else:
              total_player_minutes[player] = minutes
  season_minutes_df = pd.DataFrame(total_player_minutes.items(), columns=['player_name', 'total_minutes_played'])
  season_minutes_df['player_number'] = season_minutes_df['player_name'].map(player_numbers)

  sorted_minutes_df = season_minutes_df.sort_values(by='total_minutes_played',ascending=False)
  top_eleven_players = sorted_minutes_df.head(11)
  return top_eleven_players,sorted_minutes_df


def draw_initial_xi(xi_df,team,c1,c2):
    pitch = VerticalPitch(pitch_color='#1B2632', line_color='#EEE9DF', pitch_type='opta',linewidth=0.5,goal_type='box')
    fig, ax = pitch.draw(figsize=(12, 6))
    fig.set_facecolor('#1B2632')
    ax.set_facecolor('#1B2632')
    nodes = pitch.scatter(xi_df.x,xi_df.y,
                            ax=ax,
                            s=420, color=c1,edgecolors=c2,linewidth=1,zorder=1)


    for index, row in xi_df.iterrows():
        pitch.annotate(row.player_number, xy=(row.x,row.y), c=c2,zorder=4,
                    va='center', ha='center', size=9,ax=ax, fontweight= 'bold')
        words = row.player_name.split()
        if len(words)>1:
            first_letters = ''.join(word[0] for word in words[:-1])
            row.player_name= f"{first_letters}.{words[-1]}"
        if row.x > np.mean(xi_df['x']):
            pitch.annotate(row.player_name, xy=(row.x+4,row.y), c='#EEE9DF',zorder=4,
                        va='center', ha='center', size=10,ax=ax, fontweight= 'bold')

        else:
            pitch.annotate(row.player_name, xy=(row.x-4,row.y), c='#EEE9DF',zorder=4,
                        va='center', ha='center', size=10,ax=ax, fontweight= 'bold')

    plt.title(f'{team} most frequent XI',loc='center', fontweight='bold',color='white')

    return fig

##### MATCHES
def match_info(home,away,season):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
    SELECT match_event.*, players.name AS player_name, teams.name AS team_name
    FROM match_event
    JOIN matches ON match_event.match_id = matches.match_id
    JOIN players ON match_event.player_id = players.player_id
    JOIN teams ON match_event.team_id = teams.team_id
    WHERE matches.home = '{home}' AND matches.away = '{away}'
    AND matches.season = '{season}'
    """)
    records = cursor.fetchall()
    xT = pd.read_csv("imgs_app/xT_Grid.csv")
    xT = np.array(xT)
    xT_rows, xT_cols = xT.shape
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    df_pass = df.loc[(df['type']=="Pass") & (df['outcome']=='Successful')].reset_index()
    df_pass['x1_bin'] = pd.cut(df_pass['x'], bins=xT_cols, labels=False)
    df_pass['y1_bin'] = pd.cut(df_pass['y'], bins=xT_rows, labels=False)
    df_pass['x2_bin'] = pd.cut(df_pass['end_x'], bins=xT_cols, labels=False)
    df_pass['y2_bin'] = pd.cut(df_pass['end_y'], bins=xT_rows, labels=False)

    df_pass['start_zone_value'] = df_pass[['x1_bin', 'y1_bin']].apply(lambda x: xT[x[1]][x[0]], axis=1)
    df_pass['end_zone_value'] = df_pass[['x2_bin', 'y2_bin']].apply(lambda x: xT[x[1]][x[0]], axis=1)
    df_pass['xT'] = df_pass['end_zone_value'] - df_pass['start_zone_value']
    game_totals = df_pass.groupby('player_name').agg({'xT':['sum']})
    game_totals.sort_values(by=('xT','sum'),ascending=False)
    

    pass_data_1 = df[df['team_name']==home].reset_index()
    pass_data_2 = df[df['team_name']==away].reset_index()

    return pass_data_1,pass_data_2,df_pass

def pass_network(df,df_pass,team,opponent,minimum,color1,color2,team_img):
  team = team
  df['passer'] = df['player_name']
  df['recipient'] = df['player_name'].shift(-1)

  team_against = opponent
  subs1 = df[df['team_name']==team]
  subs1 = subs1[subs1['type']=='SubstitutionOff']
  firstSub = subs1['minute']
  firstSub=firstSub.min()
  if firstSub<30:
      firstSub =45
  succesful = df[df['minute']<firstSub]
  average_locations = succesful.groupby('passer').agg({'x':['mean'],'y':['mean','count']})

  # x Threat summatory team (highest xT of the whole match)
  x_threat = df_pass[df_pass['team_name']==team]
  x_threat = x_threat.groupby('player_name').agg({'xT':['sum']})
  x_threat.columns=['sum']
  x_threat = x_threat.sort_values(by='sum',ascending=False)
  highest_xT = x_threat.iloc[0]

  highest_xT_name = highest_xT.name
  highest_xT_value = round(highest_xT['sum'],2)

  average_locations.columns=['x','y','count']
  average_locations = average_locations.sort_values(by='count', ascending=False)


  # Calculate highest nº of passes of the match
  passer_df =  df.groupby('passer').agg({'x':['mean'],'y':['mean','count']})
  passer_df.columns=['x','y','count']

  passer_df = passer_df.sort_values(by='count', ascending=False)

  highest_passer = passer_df.iloc[0]
  highest_passer_name = highest_passer.name
  highest_passer_passes = int(highest_passer['count'])

  # Pass between calculation
  pass_between = succesful.groupby(['passer','recipient']).id.count().reset_index()
  pass_between.rename({'id':'pass_count'},axis='columns',inplace=True)

  pass_between = pass_between.merge(average_locations, left_on='passer',right_index=True)
  pass_between = pass_between.merge(average_locations, left_on='recipient',right_index=True,suffixes=['','_end'])

  pass_between = pass_between[pass_between['pass_count']>minimum]


  # Plot the pitch
  pitch = VerticalPitch(pitch_color='#1B2632', line_color='#EEE9DF', pitch_type='opta',linewidth=0.5,goal_type='box')
  fig, ax = pitch.draw(figsize=(12, 6))
  fig.set_facecolor('#1B2632')
  ax.set_facecolor('#1B2632')
  pitch.annotate(f"0-{firstSub} \'", xy=(96,50), c='white',zorder=2,
                    va='center', ha='center', size=10,ax=ax)

  arrows = pitch.arrows(pass_between.x,pass_between.y,pass_between.x_end,pass_between.y_end,
                        ax=ax, lw=3,
                        width=3,headwidth=3,headlength=4,
                        color='#B2FFA9',zorder=1,alpha=(pass_between.pass_count / pass_between.pass_count.max()))

  x_threat = df_pass[(df_pass['team_name']==team) & (df_pass['minute']<firstSub)]
  x_threat = x_threat.groupby('player_name').agg({'xT':['sum']})
  x_threat.columns=['sum']

  average_locations = average_locations.merge(x_threat, left_on='passer', right_index=True)

  nodes = pitch.scatter(average_locations.x,average_locations.y,
                        ax=ax,
                        s=200+(800*average_locations['sum']), color=color1,edgecolors=color2,linewidth=1,zorder=1)

  plt.text(-42, 67,f'{highest_passer_name}', fontsize=14, ha='center', va='center',color='white',fontfamily="Liberation Sans Narrow")
  plt.text(-15, 72,f'HIGHEST Nº OF PASSES: ', fontsize=14, ha='left', va='center',color='white',fontfamily="Liberation Sans Narrow",fontweight='bold')
  plt.text(-42, 50,f'{highest_xT_name} ({highest_xT_value})', fontsize=14, ha='center', va='center',color='white',fontproperties="Liberation Sans Narrow")
  plt.text(-15, 55,f'HIGHEST xT (via pass):', fontsize=14, ha='left', va='center',color='white',fontfamily="Liberation Sans Narrow",fontweight='bold')

  ax.set_xlim(105, -60)

  mSize = [0.05,0.20,0.6,0.8]
  mSizeS = [700 * i for i in mSize]
  mx = [-28,-33,-41,-51]
  my = [35,35,35,35]

  # Plot circles (xT) and arrow
  plt.scatter(mx, my, s=mSizeS, facecolors=color1, edgecolor=color2)
  arrow_x = -25  # X-coordinate for the arrow
  arrow_y = 30  # Y-coordinate for the arrow
  arrow = mpl.patches.FancyArrowPatch((arrow_x, arrow_y), (arrow_x-34, arrow_y), color='white',arrowstyle='-|>', mutation_scale=12, lw=1)
  plt.text(-38, 28, 'xT', va='center', fontfamily="Liberation Sans Narrow", fontsize=12,fontweight='bold',color='white')
  ax.add_patch(arrow)

  # Plot arrows intensity
  arrow = mpl.patches.FancyArrowPatch((-29, 15), (-38, 24), color='#B2FFA9',arrowstyle='-|>', mutation_scale=12, lw=4,alpha=0.2)
  ax.add_patch(arrow)
  arrow = mpl.patches.FancyArrowPatch((-38, 15), (-47, 24), color='#B2FFA9',arrowstyle='-|>', mutation_scale=12, lw=4,alpha=0.6)
  ax.add_patch(arrow)
  arrow = mpl.patches.FancyArrowPatch((-47, 15), (-56, 24), color='#B2FFA9',arrowstyle='-|>', mutation_scale=12, lw=4,alpha=1)
  ax.add_patch(arrow)

  arrow = mpl.patches.FancyArrowPatch((-25, 12), (-59, 12), color='white',arrowstyle='-|>', mutation_scale=12, lw=1,alpha=1)
  plt.text(-28, 10, 'Nº of passes', va='center', fontfamily="Liberation Sans Narrow", fontsize=12,fontweight='bold',color='white')
  ax.add_patch(arrow)

  # plot title
  plt.title(f'Pass network {team} against {team_against}',loc='center', fontweight='bold',color='white')
  plt.text(78, -5,f'*minimum 5 passes to be included', fontsize=12, ha='left', va='center',color='white',fontfamily="Liberation Sans Narrow")
  average_locations.reset_index(inplace=True)

  # Plot images
  ax3 = add_image(team_img, fig, left=0.64, bottom=0.75, width=0.075, interpolation='hanning')

  # plot player names
  for index, row in average_locations.iterrows():
    words = row.passer.split()
    if len(words)>1:
        first_letters = ''.join(word[0] for word in words[:-1])
        row.passer= f"{first_letters}.{words[-1]}"
    if row.x > np.mean(average_locations['x']):
     pitch.annotate(row.passer, xy=(row.x+4,row.y), c='#EEE9DF',zorder=4,
                    va='center', ha='center', size=9,ax=ax, fontweight= 'bold')
    else:
     pitch.annotate(row.passer, xy=(row.x-4,row.y), c='#EEE9DF',zorder=4,
                    va='center', ha='center', size=9,ax=ax, fontweight= 'bold')

  return fig



##### PLAYERS INFO 

def search_players(team,season):
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute(f"""
    SELECT DISTINCT players.name FROM match_event
    JOIN players ON match_event.player_id = players.player_id
    JOIN matches ON match_event.match_id = matches.match_id
    JOIN teams ON match_event.team_id = teams.team_id
    WHERE teams.name = '{team}' AND matches.season = '{season}'
    """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    return df['name'].to_list()


def player_heatmap(player,season):
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute(f"""
    SELECT * FROM match_event
    JOIN players ON match_event.player_id = players.player_id
    JOIN matches ON match_event.match_id = matches.match_id             
    WHERE type = 'BallTouch' AND players.name = '{player}'
    AND matches.season = '{season}'
    """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    pitch = VerticalPitch(pitch_type='opta',half=False,
            pitch_color='#1B2632',stripe=False,line_color='#EEE9DF',
            goal_type='box',linewidth=2,line_zorder=4,corner_arcs=True)

    fig, axs = pitch.draw(figsize=(10, 8))
    # Create a custom color map that goes from yellow to red
    colors = [(1, 1, 0), (1, 0, 0)]  # (R, G, B) values: yellow (1, 1, 0) to red (1, 0, 0)
    cmap = LinearSegmentedColormap.from_list("YellowToRed", colors, N=256)

    df.y = 100-df['y']
    #Create the heatmap
    kde = sns.kdeplot(df,
                      x='y',
                      y='x',
                      fill = True,
                      multiple = 'fill',
                      thresh = 0.5,
                      cmap= cmap,#turbo#magma
                      alpha = 0.8,
                      levels=800,
                      common_norm=False,cut=4
                      )

    plt.arrow(105, 30,0 , 40, color='#EEE9DF', alpha=1.0,
              zorder=1, head_width=3, head_length=3.5, linewidth=3,
              length_includes_head=True)
    plt.xlim([-5,110])
    plt.ylim([-10,100])
    plt.title(f"{player} heatmap",loc='center',y=1.03,
              fontweight='bold',color= '#EEE9DF')
    fig.set_facecolor('#1B2632')
    axs.set_facecolor('#1B2632')
    return fig

def player_passing_zones(player,season):
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute(f"""
    SELECT match_event.*, players.name AS player_name
    FROM match_event
    JOIN matches ON match_event.match_id = matches.match_id
    JOIN players ON match_event.player_id = players.player_id
    WHERE players.name = '{player}' AND matches.season = '{season}'
    """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    df_pass = df[(df['type']=='Pass') & (df['player_name'] == player) ]
    data_player = df_pass
    pitch = VerticalPitch(pitch_color='#1B2632', line_color='#EEE9DF', line_zorder=2,
                        pitch_type='opta',
                        linewidth=2,goal_type='box')

    fig, axs = pitch.draw(figsize=(10, 8))

    colors = ['#1B2632', '#8FBC8F', '#00FF00']
    cmap = LinearSegmentedColormap.from_list("DarkToBrightGreen", colors, N=256)

    hexmap = pitch.hexbin(data_player.x, data_player.y, ax=axs, edgecolors='#1B2632',
                        gridsize=(10, 10), cmap=cmap)
    fig.set_facecolor('#1B2632')
    axs.set_facecolor('#1B2632')

    plt.arrow(105,30 , 0, 40, color='#EEE9DF', alpha=1.0,
            zorder=1, head_width=3, head_length=3.5, 
            linewidth=3, length_includes_head=True)
    plt.title(f'Most frequent pass zones {player}',loc='center', y = 1.03,
               fontweight='bold',color='#EEE9DF')

    plt.xlim([-5, 110])
    plt.ylim([-10, 100])
    plt.gca().invert_xaxis()
    return fig

def player_shotmap(player,season):
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT match_event.*,players.name FROM match_event
          LEFT JOIN players ON match_event.player_id = players.player_id
          JOIN matches ON match_event.match_id = matches.match_id
          WHERE players.name = '{player}' AND match_event.is_shot = True
          AND matches.season = '{season}'
        """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    pitch = VerticalPitch(pitch_type='opta', line_zorder=2, linewidth=0.5,
              pitch_color='#1B2632', line_color='#EEE9DF',half=True,goal_type= 'box',pad_bottom=-20)

    count_g=0
    fig, ax = pitch.draw(figsize=(6.6, 5))

    fig.set_facecolor('#1B2632')
    ax.set_facecolor('#1B2632')
    def make_html(fontname):
        return "<p>{font}: <span style='font-family:{font}; font-size: 24px;'>{font}</p>".format(font=fontname)

    code = "\n".join([make_html(font) for font in sorted(set([f.name for f in matplotlib.font_manager.fontManager.ttflist]))])

    fm_rubik = FontManager('https://raw.githubusercontent.com/google/fonts/main/ofl/montserratalternates/MontserratAlternates-SemiBold.ttf' )

    for index,row in df.iterrows():
        color_choice = 'red'
        size_c = 50
        alpha_c = 0.5
        edge_c = 'none'
        if row['type'] == 'Goal':
            count_g+=1
            color_choice = '#32CD32'
            size_c= 80
            alpha_c = 0.9
            edge_c = 'black'
            plt.plot([row['y'], row['goal_mouth_y']], [row['x'],100], color='#EEE9DF', linestyle='--', linewidth=0.3, zorder=1)

        plt.scatter(row['y'],row['x'],color = color_choice,s=size_c,edgecolor=edge_c,linewidth=1,alpha=alpha_c)

    plt.title(f'{player} Shot-map {season} ',loc='center', fontweight='bold',c='#EEE9DF')
    plt.text(90, 65,f'{len(df)}', fontsize=25, ha='left', va='center',fontproperties=fm_rubik.prop,c='#EEE9DF')
    plt.text(80, 65,f'Shots ', fontsize=18, ha='left', va='center',fontfamily="Liberation Sans Narrow",c='#EEE9DF')
    plt.text(65, 65,f'{count_g}', fontsize=25, ha='left', va='center',fontproperties=fm_rubik.prop,c='#EEE9DF')
    plt.text(55, 65,f'Goals ', fontsize=18, ha='left', va='center',fontfamily="Liberation Sans Narrow",c='#EEE9DF')
    percentage = (count_g / len(df)) * 100
    formatted_percentage = f'{percentage:.1f}%' 
    plt.text(40, 65,f'{formatted_percentage}', fontsize=25, ha='left', va='center',fontproperties=fm_rubik.prop,c='#EEE9DF')
    plt.text(22, 65,f'Accuracy ', fontsize=18, ha='left', va='center',fontfamily="Liberation Sans Narrow",c='#EEE9DF')

    # Get goal parts
    df['shot_form'] = df['qualifiers'].apply(get_shot_form)
    goals_df = df.loc[df['type'] == 'Goal']
    shot_form_counts = goals_df['shot_form'].value_counts()
    count_head = shot_form_counts.get('Head', 0)
    count_left_foot = shot_form_counts.get('LeftFoot', 0)
    count_right_foot = shot_form_counts.get('RightFoot', 0)

    return fig, count_head, count_left_foot, count_right_foot

def passing_threat(player,season):
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT match_event.*,players.name FROM match_event
          LEFT JOIN players ON match_event.player_id = players.player_id
          JOIN matches ON match_event.match_id = matches.match_id
          WHERE players.name = '{player}' AND match_event.type = 'Pass'
          AND matches.season = '{season}'
        """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    df = df.loc[(df['type']=='Pass') & (df['outcome']=='Successful')].reset_index()
    xT = pd.read_csv("imgs_app/xT_Grid.csv")
    xT = np.array(xT)
    xT_rows, xT_cols = xT.shape
    df_pass = df
    df_pass['x1_bin'] = pd.cut(df_pass['x'], bins=xT_cols, labels=False)
    df_pass['y1_bin'] = pd.cut(df_pass['y'], bins=xT_rows, labels=False)
    df_pass['x2_bin'] = pd.cut(df_pass['end_x'], bins=xT_cols, labels=False)
    df_pass['y2_bin'] = pd.cut(df_pass['end_y'], bins=xT_rows, labels=False)
    df_pass['start_zone_value'] = df_pass[['x1_bin', 'y1_bin']].apply(lambda x: xT[x[1]][x[0]], axis=1)
    df_pass['end_zone_value'] = df_pass[['x2_bin', 'y2_bin']].apply(lambda x: xT[x[1]][x[0]], axis=1)
    df_pass['xT'] = df_pass['end_zone_value'] - df_pass['start_zone_value']
    df_pass = df_pass.sort_values(by='xT',ascending=False)
    count=0

    pitch = Pitch(pitch_color='#1B2632', line_color='#EEE9DF', pitch_type='opta',goal_type='box',linewidth=0.5)
    fig, axs = pitch.draw(figsize=(8, 6))
    plt.arrow(30,-5 , 40, 0, color='#EEE9DF', alpha=1.0,
            zorder=1, head_width=3, head_length=3.5, linewidth=3, length_includes_head=True)
    plt.xlim([-5, 110])
    plt.ylim([-10, 100])

    plt.title(f'Passing Threat {player} | {season} ',loc='center', fontweight='bold',fontsize=16,color="#EEE9DF")
    count_s = 0
    df_pass_filtered= df_pass.head(10)
    fig.set_facecolor('#1B2632')
    for index, row in df_pass_filtered.iterrows():
        count_s += 1
        color_choice = "#EEE9DF"
        plt.plot(row['x'], row['y'], 'o',color=color_choice,markersize=6)
        lc2 = lines(row['x'], row['y'], row['end_x'], row['end_y'], cmap='winter',
                    comet=True, transparent=True,
                    linewidth=8,
                    alpha_start=0.5, alpha_end=0.6, ax=axs)
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    df = df.loc[(df['type']=='Pass') & (df['outcome']=='Successful')].reset_index()
    df.x = df.x*1.2
    df.y = df.y*.8
    df.end_x = df.end_x*1.2
    df.end_y = df.end_y*0.8

    df['beginning'] = np.sqrt(np.square(120-df['x']) + np.square(40 - df['y']))
    df['end'] = np.sqrt(np.square(120 - df['end_x']) + np.square(40 - df['end_y']))

    df['progressive'] = [(df['end'][x]) / (df['beginning'][x]) < .75 for x in range(len(df.beginning))]

    df.loc[df['progressive']==True].outcome
    df.x = df.x/1.2
    df.y = df.y/.8
    df.end_x = df.end_x/1.2
    df.end_y = df.end_y/0.8
    data_player = df.loc[df['progressive']==True]    
    for index, row in data_player.iterrows():
        if row['id'] not in df_pass_filtered['id'].values:
            if row['progressive'] == True:
                count_s += 1
                color_choice = "#E3AF64"
                plt.plot(row['x'], row['y'], 'o',color=color_choice,markersize=1)
                plt.arrow(row['x'], row['y'], row['end_x'] - row['x'], row['end_y'] - row['y'],
                            color=color_choice, alpha=0.7, zorder=1,
                            head_width=1, head_length=1, linewidth=0.9, length_includes_head=True)


    plt.annotate('Hightest xT', xy=(0.83, 0.03), xycoords='axes fraction', ha='right', fontsize=12,color="#EEE9DF")
    plt.annotate('Progressive Passes', xy=(0.05, 0.03), xycoords='axes fraction', ha='left', fontsize=12,color='#E3AF64')
    plt.arrow(2,-8 , 20, 0, color='#E3AF64', alpha=1.0,
            zorder=1, head_width=1, head_length=1, linewidth=0.9, length_includes_head=True)
    lines(91, -5, 100, -5, cmap='winter',comet=True, transparent=True,linewidth=8,alpha_start=0.5, alpha_end=0.6, ax=axs)

    return fig

def player_dribbles(player,season):
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute(f"""
       SELECT match_event.*,players.name FROM match_event
          LEFT JOIN players ON match_event.player_id = players.player_id
          JOIN matches ON match_event.match_id = matches.match_id
          WHERE players.name = '{player}' AND match_event.type = 'TakeOn'
          AND matches.season = '{season}'
        """)
    records = cursor.fetchall()
    takeons = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    
    count=0
    pitch = VerticalPitch(pitch_color='#1B2632',line_color='#EEE9DF', pitch_type='opta',linewidth=0.5,goal_type='box')
    fig, axs = pitch.draw(figsize=(12, 6))
    plt.arrow(-7, 30, 0, 40, color='white', alpha=1.0,
            zorder=1, head_width=3, head_length=3.5, linewidth=3, length_includes_head=True)
    plt.xlim([-10, 105])
    plt.ylim([-5, 105])
    plt.gca().invert_xaxis()
    player = takeons["name"].unique()[0]
    plt.title(f'{player} dribbles {season}',loc='center', fontweight='bold',c='#EEE9DF')
    count_s = 0
    total = len(takeons)
    fig.set_facecolor('#1B2632')


    for index, row in takeons.iterrows():
        if row['outcome'] == 'Successful':
            count_s += 1
            plt.plot(row['y'], row['x'], 'o',color='#33FF9C',markersize=10,markeredgecolor="#00CC69",zorder=2)
        if row['outcome'] == 'Unsuccessful':
            plt.plot(row['y'], row['x'], 'o',color='#F40101',markersize=7,alpha=0.5,zorder=1)
    percentage=(count_s/total)*100
    legend_labels = [f'Totals: {count_s}/{total}  ({percentage:.1f}%)']
    plt.legend(legend_labels,bbox_to_anchor=(0.92, 0.043), loc='lower right',handlelength=0, handleheight=0)

    return fig
def player_passmap(player,home,opponent,mode,season):
    conn = create_connection() 
    cursor = conn.cursor()
    cursor.execute(f"""
    SELECT match_event.*, players.name AS player_name
    FROM match_event
    JOIN matches ON match_event.match_id = matches.match_id
    JOIN players ON match_event.player_id = players.player_id
    WHERE matches.home = '{home}' AND matches.away = '{opponent}'  AND matches.season ='{season}'
    AND players.name ='{player}'
    """)
    records = cursor.fetchall()
    df = pd.DataFrame(records, columns = [desc[0] for desc in cursor.description])
    df_pass = df[(df['type']=='Pass') & (df['player_name'] == player) ]
    if len(df)==0:
        return "Not valid"
    else:
        goal_indices = df[df['type'] == 'Goal'].index
        assist_indexes = []
        for goal_index in goal_indices:
            for i in range(goal_index, -1, -1):
                if df.at[i, 'type'] == 'Pass':
                    assist_indexes.append(i)
                    break
        count=0
        data_player = df_pass
        pitch = VerticalPitch(pitch_color='#1B2632', line_color='#EEE9DF', pitch_type='opta',linewidth=0.5,goal_type='box')

        fig, axs = pitch.draw(figsize=(10, 8))
        fig.set_facecolor('#1B2632')
        axs.set_facecolor('#1B2632')
        plt.arrow(105,30 , 0, 40, color='#EEE9DF', alpha=1.0,
                zorder=1, head_width=3, head_length=3.5, linewidth=3, length_includes_head=True)
        plt.xlim([-5, 110])
        plt.ylim([-10, 100])
        plt.gca().invert_xaxis()
        if mode == "Away":
            plt.title(f'Pass map {player} vs {home} ',loc='center', fontweight='bold',color='#EEE9DF')
        else:
            plt.title(f'Pass map {player} vs {opponent} ',loc='center', fontweight='bold',color='#EEE9DF')
        count_s = 0
        total = len(data_player)
        for index, row in data_player.iterrows():
            if row['outcome'] == 'Successful':
                count_s += 1
                color_choice = "#0AFF3B"
                alpha_choice = 0.8
                if index in assist_indexes:
                    color_choice= "yellow"   # Is Assist
                    alpha_choice = 1
                plt.plot(row['y'], row['x'], 'o',color=color_choice,markersize=2)
                plt.arrow(row['y'], row['x'], row['end_y'] - row['y'], row['end_x'] - row['x'],
                        color=color_choice, alpha= alpha_choice, zorder=1,
                        head_width=0.8, head_length=1, linewidth=1.2, length_includes_head=True)
            elif row['outcome'] == 'Unsuccessful':
                    plt.arrow(row['y'], row['x'], row['end_y'] - row['y'], row['end_x'] - row['x'],
                        color='red', alpha=0.5, zorder=1,
                        head_width=0.8, head_length=1, linewidth=1.2, length_includes_head=True)
        percentage=(count_s/total)*100
        legend_labels = [f'Totals: {count_s}/{total}  ({percentage:.1f}%)']
        plt.legend(legend_labels,bbox_to_anchor=(0.95, 0.09), loc='lower right',handlelength=0, handleheight=0)
        
    return fig

