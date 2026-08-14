# prompt

I am part of a hackathon right now. We want to make a project called CVlizer.

stack: cognee, qdrant, slack

The basic idea is that we are the HR department of a big tech corp and we use CVlizer to ingest applicant CVs, store them using Congee and Qdrant and use slack to query available CVs.

Participants in the Slack channel are HR people, hiring manager and developers who are in need of developers with specific skills/profiles in their teams.

## CV uploading

CVs are uploaded manually for now into Qdrant using a Python script. Later we can link an email inbox or a web form.

## Jop posting

There is a slack channel where the user (HR-manager) post a job description. The job should be parsed and indexed in Qdrant using Cognee. After indexing the job, cognee searches the best matches for the job in qdrant containing the candidates CVs. Finally cognee should post the best matches in the slack channel.

The match will be based on the skills and experience of the candidates. 

Create a plan for a hackathon project that matches job seekers with jobs based on their skills and experience.

