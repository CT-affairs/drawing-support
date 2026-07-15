FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY liff3 /usr/share/nginx/html/liff3

EXPOSE 8080
