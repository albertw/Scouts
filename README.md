## check_all_renewals.py

This script will analyse the Member-Trainings-Report and Member-Vetting-Report spreadsheets that can be downloaded from the Scouting Ireland MMS at my.scouts.ie and will print the names and details of any scouters that have either Vetting or Safeguarding renewals due in the next 3 months.

## scouts_courses_scraper.py

One thing Scouting Ireland seems incapable of doing is giving group leaders a current list of upcoming courses nationally. This would be really useful for Group Leaders when trying to get new volunteers on 'Being A Scouter' courses, especially where doing the course in a neighbouring scout province would suit the volunteer.

So this script scrapes through my.scouts.ie looking for training courses and sumps them out in a csv file.

The mechanics of this we were written with cluade code /z.ai. I was getting nowhere with figuring out this mainly javascript page on my own! Interestingly though the AI really overcomplicated the parse_course_info which I've greatly simplified.

This does require a Group Leader login. credentials should be stored in a config.json

This will all break as they update the website btw :)