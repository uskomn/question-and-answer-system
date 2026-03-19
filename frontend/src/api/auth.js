import apiClient from './client'

export default{
    login(username,password){
        return apiClient.post('auth/login',{
            username,
            password
        })
    },
    register(username,email,password){
        return apiClient.post('auth/register',{
            username,
            email,
            password
        })
    }
}