# prompt

create a plan for a hackathon project that matches job seekers with jobs based on their skills and experience.

stack: cognee, qdrant, slack

There is a slack channel where the user (HR-manager) post a job description. The job should be parsed and indexed in Qdrant using Cognee. After indexing the job, the cognee also search the best matches for the job in a vector-db containing the candidates resumes. Finally the cognee should post the best matches in the slack channel.

The match will be skill based on the skills and experience of the candidates. 



