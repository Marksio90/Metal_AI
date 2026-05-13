FROM node:20-alpine

WORKDIR /app

COPY apps/frontend/package*.json ./
RUN npm install

COPY apps/frontend .

# NEXT_PUBLIC_* variables must be present at build time — they are inlined into
# the JS bundle by Next.js and cannot be injected at runtime via env_file.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start", "--", "-p", "3000"]
