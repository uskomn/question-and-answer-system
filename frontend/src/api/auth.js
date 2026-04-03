import apiClient from './client'

export default{
    login(username,password){
        return apiClient.post('auth/login',{
            username,
            password
        })
    },
    send_code(email){
        return apiClient.post('auth/send_code',{
            email
        })
    },
    register(username,email,password,code){
        return apiClient.post('auth/register',{
            username,
            email,
            password,
            code
        })
    }
}