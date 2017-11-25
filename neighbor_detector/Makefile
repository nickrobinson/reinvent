deploy:
	rm lambda.zip
	zip lambda.zip lambda_function.py
	aws lambda update-function-code --function-name iot_rekognition --zip-file fileb:///Users/nickrobi/Desktop/reinvent/neighbor_detector/lambda.zip --region us-east-1
