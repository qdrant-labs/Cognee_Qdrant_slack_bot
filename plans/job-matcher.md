# MVP

I am part of a hackathon right now. We want to make a project called CVlizer.

stack: cognee, qdrant, slack, Groq API for cognee

The basic idea is that we are the HR department of a big tech corp and we use CVlizer to ingest applicant CVs, store them using Congee and Qdrant and use slack to query available CVs.

Participants in the Slack channel are HR people, hiring manager and developers who are in need of developers with specific skills/profiles in their teams.

## CV uploading

CVs are uploaded manually for now into Qdrant using a Python script.

## Jop posting

There is a slack channel where the user (HR-manager) post a job description. The job should be parsed and indexed in Qdrant using Cognee. After indexing the job, cognee searches the best matches for the job in qdrant containing the candidates CVs.

## Matchmaking
After a job is posted and indexed in Qdrant, Cognee searches the best matches for the job in qdrant containing the candidates CVs. After that, on Slack the bot should post the best matches. matches should be the top 3 candidates and it should include name, matching-points (CVs quotes), matching score, reason to hire.

The match will be based on the skills and experience of the candidates. 

# Future plans

DO NOT IMPLEMENT ANY OF THIS!!!

 Just keep it into account for architecting the project.

- Link an email inbox or a web form and ingest CVs automatically.

- Interview minutes will also be logged and performance will be taken into account for matchmaking.

- Talent pool: Store CVs for X years and notify job-posters about pool candidates that match the job profile.

- Take public presence of candidate (articles, repos, etc) into account for matchmaking.


---

Create a plan for a hackathon project that matches job seekers with jobs based on their skills and experience.
