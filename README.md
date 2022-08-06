# deployment project

## To build a deployment flow please do next steps:

### 1. Create a codebuild project with some name
   #### 1.1. In the **source** section choose **No source** option
   #### 1.2. In the environment section choose whatever you want.
    Preferable, 
    Managed image -> Amazon Linux 2, 
    Runtimes -> Standard, 
    Image -> aws/codebuild/amazonlinux2-x86_64-standard:3.0, 
    Image version -> Always the last image version, 
    Service role -> create new one or use existed one (do not forget that this role should have an access for bunch of other services such as DynamoDB, S3, CodeBuild, Lambda)
   #### 1.3. For the Buildspec. As we choose **No source** option in **source** section you should paste the code from buildspec.yaml file in this repo to codebuild editor in this section. It is the name of the bucket name inside the buildspec.yaml. Be sure that you have execution python file inside this S3 bucket. 
   #### 1.4. Everything else could be as it is.
   #### 1.5. Add environment variables for github-token, dynamodb table name and aws regions. The list of variables are below
```
      github_token
      metadata_table
      dev_region
      beta_region
      prod_region
```
   #### 1.6. Create a trigger for the codebuild. 

### 2. Create a S3 bucket with a name specified in the buildspec.yaml file.
### 3. Create a DynamoDB table with the same name as was specified in the environment variables in the codebuild project.

