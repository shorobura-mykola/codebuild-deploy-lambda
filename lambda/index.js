exports.handler = async (event) => {
  const response = {
    statusCode: 200,
    body: JSON.stringify('Test your lambda deployment using AWS CodeBuild'),
  };
  return response;
};