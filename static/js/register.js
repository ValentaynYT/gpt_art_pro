function checkPassword(form) {
    password1 = form.password1.value;
    password2 = form.password2.value; 
    if (password1 != password2) {
        alert("\nПароли не совпадают: Пожалуйста попробуйте еще раз")
        return false;
    }
    else {
        alert("Пароли совпадают: Добро пожаловать! ")
        return true;
    }
}