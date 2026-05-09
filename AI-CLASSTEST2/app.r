if (.Platform$OS.type == "windows") {
  system("cmd /c start python ai_engine.py", wait = FALSE)
  system("cmd /c start python dashboard.py", wait = FALSE)
} else {
  system("python3 ai_engine.py &", wait = FALSE)
  system("python3 dashboard.py &", wait = FALSE)
}
library(shiny)
library(ggplot2)
library(dplyr)
library(gridExtra)

CSV_FILE <- "emotion_log.csv"

ui <- fluidPage(
  titlePanel("Professor Dashboard: Attendance & Stats"),
  
  sidebarLayout(
    sidebarPanel(
      actionButton("refresh", "Update Live Feed"),
      downloadButton("report", "Generate PDF Report"),
      hr(),
      h4("Attendance"),
      tableOutput("attendance_list")
    ),
    
    mainPanel(
      plotOutput("trendPlot"),
      h4("BA304 Statistical Summary"),
      tableOutput("stats_table")
    )
  )
)

server <- function(input, output) {
  
  data_load <- reactive({
    input$refresh
    
    req(file.exists(CSV_FILE))
    
    df <- read.csv(CSV_FILE, stringsAsFactors = FALSE)
    
    req(nrow(df) > 0)
    req(all(c("Student_ID", "Emotion", "Confidence") %in% names(df)))
    
    df <- df %>%
      mutate(
        Emotion = tolower(trimws(Emotion)),
        Confidence = suppressWarnings(as.numeric(Confidence)),
        Confidence = ifelse(is.na(Confidence), 0, Confidence)
      )
    
    df %>% mutate(
      EmotionWeight = case_when(
        Emotion %in% c("happy", "neutral", "surprise") ~ 1.0,
        Emotion %in% c("sad", "angry", "fear", "disgust") ~ 0.2,
        TRUE ~ 0.5
      ),
      Score = pmin(1, pmax(0, EmotionWeight * Confidence))
    )
  })
  
  output$attendance_list <- renderTable({
    data_load() %>%
      group_by(Student_ID) %>%
      summarize(Engagement = round(mean(Score), 2))
  })
  
  output$stats_table <- renderTable({
    df <- data_load()
    
    m <- mean(df$Score, na.rm = TRUE)
    s <- sd(df$Score, na.rm = TRUE)
    cv <- ifelse(m == 0, NA, (s / m) * 100)
    
    data.frame(
      Metric = c("Mean Engagement", "Consistency (CV %)"),
      Value = c(
        round(m, 2),
        ifelse(is.na(cv), "N/A", paste0(round(cv, 1), "%"))
      )
    )
  })
  
  output$trendPlot <- renderPlot({
    df <- data_load()
    
    ggplot(df, aes(x = 1:nrow(df), y = Score, color = Student_ID)) + 
      geom_line() +
      theme_minimal() +
      labs(
        x = "Time",
        y = "Engagement",
        title = "Live Student Trends"
      )
  })
  
  output$report <- downloadHandler(
    filename = function() {
      paste("Class_Report_", Sys.Date(), ".pdf", sep = "")
    },
    
    content = function(file) {
      pdf(file, width = 8, height = 11)
      
      df <- data_load()
      
      plot.new()
      text(0.5, 0.9, "Automated Classroom Analysis Report", cex = 1.5, font = 2)
      text(0.5, 0.8, paste("Mean Engagement:", round(mean(df$Score), 2)))
      
      p1 <- ggplot(df, aes(x = Emotion, fill = Emotion)) +
        geom_bar() +
        labs(title = "Overall Emotion Distribution")
      
      print(p1)
      
      dev.off()
    }
  )
}

runApp(list(ui = ui, server = server), 
  host = "0.0.0.0", 
  port = 1234, 
  launch.browser = TRUE)
