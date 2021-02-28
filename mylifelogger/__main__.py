import click
from colorama import init, Fore, Style
import re
from mylifelogger.models import ReminderDates, Event
import datetime
from mylifelogger import session_factory, BASEDIR
from os.path import join as path_join
from dateutil.relativedelta import relativedelta
from mylifelogger.exceptions import InvalidFormat, InvalidDate
import pickle
import os


def query_data(id=None):
    if id is None:
        session = session_factory()
        return session.query(Event).order_by(Event.date_created).all()


def print_date(years, months, days):
    print('Every ', end='')
    if years > 0:
        print(years, 'year', end='')
        if months:
            print(end=', ')
    if months > 0:
        print(months, 'month', end='')
        if days:
            print(end=', ')
    if days > 0:
        print(days, 'day', end='')


def read_markdown():
    path = path_join(BASEDIR, 'markdown', 'description.md')
    with open(path) as file:
        des = file.read()
    return des


def create_dir_if_not_exists(path: str, dirname: str) -> str:
    dir_path = path_join(path, dirname)
    try:
        os.mkdir(dir_path)
    except FileExistsError:
        pass
    return dir_path


def unpickle_object():
    path = path_join(BASEDIR, 'cache', '__object__.cache')
    if os.path.exists(path):
        with open(path, 'rb') as file:
            out = pickle.load(file)
    else:
        out = False
    return out


def pickle_object(obj: dict) -> None:
    path = create_dir_if_not_exists(BASEDIR, 'cache')
    path = path_join(path, '__object__.cache')

    with open(path, 'wb') as pickle_out:
        pickle.dump(obj, pickle_out)


def parse_date(str_date):
    if str_date:
        # str_date format => dd-mm-yyyy
        str_date = str_date.split('-')
        try:
            str_date = [int(x) for x in str_date]
            str_date = datetime.date(*str_date[::-1])
        except ValueError:
            raise InvalidFormat(f'Date not in valid format')

        if str_date > datetime.date.today():
            raise InvalidDate(
                'Date created cannot be greater than today\'s date')
    else:
        str_date = datetime.date.today()
    return str_date


def parse_remind_syntax(code):
    pattern = r'period[ ]*=[ ]*\(([0-9 ]+,[0-9 ]+,[0-9 ]+)\)[ ]*,[ ]*repeat[ ]*=[ ]*([0-9*]+)'
    tree = re.findall(pattern, code)

    try:
        assert len(tree[0]) == 2
        date = [int(n) for n in tree[0][0].split(',')]
        assert len(date) == 3
        if not tree[0][1] == '*':
            repeat = int(tree[0][1])
        else:
            repeat = True
    except:
        print(tree)
        raise click.UsageError(f'"{code}" is not a valid command')
    if not any(date):
        raise click.UsageError(
            'At least one value of period should be non-zero')
    return date, repeat


def prompt(text):
    user_input = input(
        f'{Fore.RED}{Style.BRIGHT}?{Style.RESET_ALL} {text}: {Fore.CYAN}')
    print(Style.RESET_ALL, end='')
    return user_input


@click.group()
@click.version_option()
def cli():
    """
        Creates events that are reminded to user periodically on configured email address.
    """
    pass


@cli.group()
def event():
    """
        Add, list, delete and edit events
    """
    pass


@event.command("new")
@click.option("-c", "--commit", is_flag=True,
              help="Generate new event from markdown.")
def new(commit):
    """
        Create new event
    """
    if not commit:
        print(f'{Fore.LIGHTYELLOW_EX}Date Format: dd-mm-yyyy{Style.RESET_ALL}')
        print(
            f'{Fore.MAGENTA}Leave any date field empty for today\'s date{Style.RESET_ALL}\n')
        while True:
            title = prompt('title')
            if not len(title) > 0:
                print(f'{Fore.RED}Title cannot be left blank{Style.RESET_ALL}')
            else:
                break
        short_description = prompt('short-description')
        date_created = prompt('date-of-event')
        base_date = prompt('base-date(Default: date-of-event)')

        if not short_description:
            short_description = title
        try:
            date_created = parse_date(date_created)
        except Exception as e:
            raise click.UsageError(f'{Fore.RED}{e}{Style.RESET_ALL}')
        if not base_date:
            base_date = date_created

        syntax = 'period = (years:int, months:int, days:int), repeat = (int|*)'
        print(
            f'\n{Fore.MAGENTA}Date are calculated for time after `base-date`{Style.RESET_ALL}')
        print(Fore.LIGHTYELLOW_EX+'Syntax: ')
        print(syntax+Style.RESET_ALL)
        print(f'{Fore.MAGENTA}Enter q to exit{Style.RESET_ALL}\n')

        event = Event(title, short_description,
                      long_description='', date_created=date_created)
        model_objects = {'event': event, 'reminder_dates': []}
        while True:
            date = prompt('remind-on')
            if len(model_objects['reminder_dates']) >= 1 and date.lower() == 'q':
                break
            try:
                delta_dates, repeat = parse_remind_syntax(date)
            except click.UsageError as e:
                print(f'{Fore.RED}ERROR: {e}{Style.RESET_ALL}')
                continue
            tdelta = relativedelta(
                days=delta_dates[2], months=delta_dates[1], years=delta_dates[0])
            reminder_date = tdelta + base_date
            print((f'{Fore.RED}next reminder on => {reminder_date.strftime("%d-%m-%Y")}'
                   f'{Style.RESET_ALL}'))

            if repeat == True:
                reminder = ReminderDates(event=event, repeat_forever=repeat,
                                         date=reminder_date, year_delta=delta_dates[0],
                                         month_delta=delta_dates[1], day_delta=delta_dates[2])
            else:
                reminder = ReminderDates(event=event, repeat=repeat,
                                         date=reminder_date, year_delta=delta_dates[0],
                                         month_delta=delta_dates[1], day_delta=delta_dates[2])

            model_objects['reminder_dates'].append(reminder)

        markdown_file = path_join(BASEDIR, 'markdown/description.md')
        with open(markdown_file, 'w') as file:
            file.write('')

        pickle_object(model_objects)

        print(f'{Style.DIM}Created `description.md` file')
        print('Run following commands to complete event creation:')
        print(f'Edit the file with suitable description{Style.RESET_ALL}')
        print(f'\n>> {Fore.LIGHTBLUE_EX}nano {markdown_file}{Style.RESET_ALL}')
        print(f'>> {Fore.LIGHTBLUE_EX}mll event new --markdown{Style.RESET_ALL}')

    else:
        model_objects = unpickle_object()
        if not model_objects:
            raise click.BadOptionUsage(option_name='markdown',
                                       message=('Unable to find cached object.'
                                                ' Run command without `-c/--commit` flag first.'))
        os.remove(path_join(BASEDIR, 'cache', '__object__.cache'))

        event = model_objects['event']

        event.long_description = read_markdown()
        session = session_factory()
        session.add(event)
        for model in model_objects['reminder_dates']:
            session.add(model)
        session.commit()
        session.close()
        print('Event successfully commited.')


@event.command('list')
@click.option('--oneline', is_flag=True, help='Single line output')
def read_data(oneline):
    """
        List all events.
    """
    for event in query_data():
        print(
            f'{Fore.LIGHTYELLOW_EX}{event.id}{Style.RESET_ALL}'
            f' {Fore.RED}{event.title}{Style.RESET_ALL}  '
            f'({event.date_created.strftime("%B %d, %Y")})')
        if not oneline:
            print(
                f'  {Fore.LIGHTYELLOW_EX}Short Description: {Style.RESET_ALL}', end='')
            print(event.short_description)
            print(f'  {Fore.LIGHTYELLOW_EX}Reminders: {Style.RESET_ALL}')
            for reminder in event.reminder_dates:
                print('    ', end='')
                print_date(reminder.year_delta,
                           reminder.month_delta, reminder.day_delta)
                if reminder.repeat_forever == True:
                    print(' (Forever)')
                else:
                    print(f' (repeats {reminder.repeat} times)')
        if not oneline:
            print()


if __name__ == '__main__':

    print('HERE')
    init()