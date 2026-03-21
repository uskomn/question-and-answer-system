import apiClient from './client'

export default {

  health() {
    return apiClient.get('/health/health')
  },

  modelInfo() {
    return apiClient.get('/info/model/info')
  },

  predict(question, context) {
    return apiClient.post('/predict/predict', {
      question,
      context,
      params: {
        temperature: 0.7,
        max_answer_len: 50
      }
    })
  },
  qa(question){
    return apiClient.post('/qa/question_answer',{
      question
    })
  }
}